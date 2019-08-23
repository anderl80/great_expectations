import pytest

import os

try:
    from unittest import mock
except ImportError:
    import mock

from great_expectations.exceptions import DataContextError
from great_expectations.datasource.generator import SubdirReaderGenerator, GlobReaderGenerator, DatabricksTableGenerator


def test_file_kwargs_generator(data_context, filesystem_csv):
    base_dir = filesystem_csv

    data_context.add_datasource("default", "pandas", base_directory=str(base_dir))
    datasource = data_context.datasources["default"]
    generator = datasource.get_generator("default")
    known_data_asset_names = datasource.get_available_data_asset_names()

    assert known_data_asset_names["default"] == {"f1", "f2", "f3"}

    f1_batches = [batch_kwargs for batch_kwargs in generator.get_iterator("f1")]
    assert len(f1_batches) == 1
    assert "timestamp" in f1_batches[0]
    del f1_batches[0]["timestamp"]
    assert f1_batches[0] == {
            "path": os.path.join(base_dir, "f1.csv"),
            "sep": None,
            "engine": "python"
        }

    f3_batches = [batch_kwargs["path"] for batch_kwargs in generator.get_iterator("f3")]
    expected_batches = [
        {
            "path": os.path.join(base_dir, "f3", "f3_20190101.csv")
        },
        {
            "path": os.path.join(base_dir, "f3", "f3_20190102.csv")
        }
    ]
    for batch in expected_batches:
        assert batch["path"] in f3_batches
    assert len(f3_batches) == 2


def test_file_kwargs_generator_error(data_context, filesystem_csv):
    base_dir = filesystem_csv
    data_context.add_datasource("default", "pandas", base_directory=str(base_dir))

    with pytest.raises(DataContextError) as exc:
        data_context.get_batch("f4")
        assert "f4" in exc.message


def test_glob_reader_generator(tmp_path_factory):
    """Provides an example of how glob generator works: we specify our own
    names for data_assets, and an associated glob; the generator
    will take care of providing batches consisting of one file per
    batch corresponding to the glob."""
    
    basedir = str(tmp_path_factory.mktemp("test_glob_reader_generator"))

    with open(os.path.join(basedir, "f1.blarg"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f2.csv"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f3.blarg"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f4.blarg"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f5.blarg"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f6.blarg"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f7.xls"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f8.parquet"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f9.xls"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f0.json"), "w") as outfile:
        outfile.write("\n\n\n")

    g2 = GlobReaderGenerator(base_directory=basedir, asset_globs={
        "blargs": {
            "glob": "*.blarg"
        },
        "fs": {
            "glob": "f*"
        }
    })

    g2_assets = g2.get_available_data_asset_names()
    assert g2_assets == {"blargs", "fs"}

    with pytest.warns(DeprecationWarning):
        # This is an old style of asset_globs configuration that should raise a deprecationwarning
        g2 = GlobReaderGenerator(base_directory=basedir, asset_globs={
            "blargs": "*.blarg",
            "fs": "f*"
        })
        g2_assets = g2.get_available_data_asset_names()
        assert g2_assets == {"blargs", "fs"}

    blargs_kwargs = [x["path"] for x in g2.get_iterator("blargs")]
    real_blargs = [
        os.path.join(basedir, "f1.blarg"),
        os.path.join(basedir, "f3.blarg"),
        os.path.join(basedir, "f4.blarg"),
        os.path.join(basedir, "f5.blarg"),
        os.path.join(basedir, "f6.blarg")
    ]
    for kwargs in real_blargs:
        assert kwargs in blargs_kwargs

    assert len(blargs_kwargs) == len(real_blargs)


def test_glob_reader_generator_customize_partitioning():
    from dateutil.parser import parse as parse

    # We can subclass the generator to change the way that it builds partitions
    class DateutilPartitioningGlobReaderGenerator(GlobReaderGenerator):
        def _partitioner(self, path, glob_):
            return parse(path, fuzzy=True).strftime("%Y-%m-%d")

    glob_generator = DateutilPartitioningGlobReaderGenerator("test_generator")  # default asset blob is ok

    with mock.patch("glob.glob") as mock_glob:
        mock_glob_match = [
            "20190101__my_data.csv",
            "20190102__my_data.csv",
            "20190103__my_data.csv",
            "20190104__my_data.csv",
            "20190105__my_data.csv"
        ]
        mock_glob.return_value = mock_glob_match
        default_asset_kwargs = [kwargs for kwargs in glob_generator.get_iterator("default")]

    partitions = set([kwargs["partition_id"] for kwargs in default_asset_kwargs])

    # Our custom partitioner will have used dateutil to parse. Note that it can then use any date format we chose
    assert partitions == {
        "2019-01-01",
        "2019-01-02",
        "2019-01-03",
        "2019-01-04",
        "2019-01-05",
    }

    with mock.patch("glob.glob") as mock_glob:
        mock_glob_match = [
            "/data/project/asset/20190101__my_data.csv",
            "/data/project/asset/20190102__my_data.csv",
            "/data/project/asset/20190103__my_data.csv",
            "/data/project/asset/20190104__my_data.csv",
            "/data/project/asset/20190105__my_data.csv"
        ]
        mock_glob.return_value = mock_glob_match
        default_asset_kwargs = [kwargs for kwargs in glob_generator.get_iterator("default")]


def test_file_kwargs_generator_extensions(tmp_path_factory):
    """csv, xls, parquet, json should be recognized file extensions"""
    basedir = str(tmp_path_factory.mktemp("test_file_kwargs_generator_extensions"))

    # Do not include: invalid extension
    with open(os.path.join(basedir, "f1.blarg"), "w") as outfile:
        outfile.write("\n\n\n")
    # Include
    with open(os.path.join(basedir, "f2.csv"), "w") as outfile:
        outfile.write("\n\n\n")
    # Do not include: valid subdir, but no valid files in it
    os.mkdir(os.path.join(basedir, "f3"))
    with open(os.path.join(basedir, "f3", "f3_1.blarg"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f3", "f3_2.blarg"), "w") as outfile:
        outfile.write("\n\n\n")
    # Include: valid subdir with valid files
    os.mkdir(os.path.join(basedir, "f4"))
    with open(os.path.join(basedir, "f4", "f4_1.csv"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f4", "f4_2.csv"), "w") as outfile:
        outfile.write("\n\n\n")
    # Do not include: valid extension, but dot prefix
    with open(os.path.join(basedir, ".f5.csv"), "w") as outfile:
        outfile.write("\n\n\n")
    
    # Include: valid extensions
    with open(os.path.join(basedir, "f6.tsv"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f7.xls"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f8.parquet"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f9.xls"), "w") as outfile:
        outfile.write("\n\n\n")
    with open(os.path.join(basedir, "f0.json"), "w") as outfile:
        outfile.write("\n\n\n")

    g1 = SubdirReaderGenerator(base_directory=basedir)

    g1_assets = g1.get_available_data_asset_names()
    assert g1_assets == {"f2", "f4", "f6", "f7", "f8", "f9", "f0"}


def test_databricks_generator():
    generator = DatabricksTableGenerator()
    available_assets = generator.get_available_data_asset_names()

    # We have no tables available
    assert available_assets == set()

    databricks_kwargs_iterator = generator.get_iterator("foo")
    kwargs = [batch_kwargs for batch_kwargs in databricks_kwargs_iterator]
    assert "timestamp" in kwargs[0]
    assert "select * from" in kwargs[0]["query"].lower()
