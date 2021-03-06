from __future__ import unicode_literals

import os
import re
import shutil
try:
    from unittest import mock
except ImportError:
    import mock

import pytest
from click.testing import CliRunner
from six import PY2

from great_expectations import DataContext
from great_expectations.cli import cli
from great_expectations.data_context.util import file_relative_path
from great_expectations.util import gen_directory_tree_str
from tests.cli.test_cli import yaml
from tests.cli.utils import assert_no_logging_messages_or_tracebacks


@pytest.mark.xfail(condition=PY2, reason="Py2")
@mock.patch("webbrowser.open", return_value=True, side_effect=None)
def test_cli_init_on_new_project(mock_webbrowser, caplog, tmp_path_factory):
    project_dir = str(tmp_path_factory.mktemp("test_cli_init_diff"))
    os.makedirs(os.path.join(project_dir, "data"))
    data_path = os.path.join(project_dir, "data", "Titanic.csv")
    fixture_path = file_relative_path(__file__, "../test_sets/Titanic.csv")
    shutil.copy(fixture_path, data_path)

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli,
        ["init", "-d", project_dir],
        input="Y\n1\n1\n{}\n\n\n\n".format(data_path, catch_exceptions=False),
    )
    stdout = result.output
    assert mock_webbrowser.call_count == 1
    assert "{}/great_expectations/uncommitted/data_docs/local_site/validations/Titanic/warning/".format(project_dir) \
           in mock_webbrowser.call_args[0][0]

    assert len(stdout) < 3000, "CLI output is unreasonably long."
    assert "Always know what to expect from your data" in stdout
    assert "What data would you like Great Expectations to connect to" in stdout
    assert "What are you processing your files with" in stdout
    assert "Enter the path (relative or absolute) of a data file" in stdout
    assert "Name the new expectation suite [Titanic.warning]" in stdout
    assert (
        "Great Expectations will choose a couple of columns and generate expectations about them"
        in stdout
    )
    assert "Generating example Expectation Suite..." in stdout
    assert "Building" in stdout
    assert "Data Docs" in stdout
    assert "A new Expectation suite 'Titanic.warning' was added to your project" in stdout
    assert "Great Expectations is now set up" in stdout

    assert os.path.isdir(os.path.join(project_dir, "great_expectations"))
    config_path = os.path.join(project_dir, "great_expectations/great_expectations.yml")
    assert os.path.isfile(config_path)

    config = yaml.load(open(config_path, "r"))
    data_source_class = config["datasources"]["files_datasource"]["data_asset_type"][
        "class_name"
    ]
    assert data_source_class == "PandasDataset"

    obs_tree = gen_directory_tree_str(os.path.join(project_dir, "great_expectations"))

    # Instead of monkey patching datetime, just regex out the time directories
    date_safe_obs_tree = re.sub(r"\d*T\d*\.\d*Z", "9999.9999", obs_tree)
    # Instead of monkey patching guids, just regex out the guids
    guid_safe_obs_tree = re.sub(
        r"[a-z0-9]{32}(?=\.(json|html))", "foobarbazguid", date_safe_obs_tree
    )
    print(guid_safe_obs_tree)
    assert (
        guid_safe_obs_tree
        == """great_expectations/
    .gitignore
    great_expectations.yml
    expectations/
        Titanic/
            warning.json
    notebooks/
        pandas/
            validation_playground.ipynb
        spark/
            validation_playground.ipynb
        sql/
            validation_playground.ipynb
    plugins/
        custom_data_docs/
            renderers/
            styles/
                data_docs_custom_styles.css
            views/
    uncommitted/
        config_variables.yml
        data_docs/
            local_site/
                index.html
                expectations/
                    Titanic/
                        warning.html
                static/
                    fonts/
                        HKGrotesk/
                            HKGrotesk-Bold.otf
                            HKGrotesk-BoldItalic.otf
                            HKGrotesk-Italic.otf
                            HKGrotesk-Light.otf
                            HKGrotesk-LightItalic.otf
                            HKGrotesk-Medium.otf
                            HKGrotesk-MediumItalic.otf
                            HKGrotesk-Regular.otf
                            HKGrotesk-SemiBold.otf
                            HKGrotesk-SemiBoldItalic.otf
                    images/
                        favicon.ico
                        glossary_scroller.gif
                        iterative-dev-loop.png
                        logo-long-vector.svg
                        logo-long.png
                        short-logo-vector.svg
                        short-logo.png
                        validation_failed_unexpected_values.gif
                    styles/
                        data_docs_custom_styles_template.css
                        data_docs_default_styles.css
                validations/
                    Titanic/
                        warning/
                            9999.9999/
                                foobarbazguid.html
        validations/
            Titanic/
                warning/
                    9999.9999/
                        foobarbazguid.json
"""
    )

    assert_no_logging_messages_or_tracebacks(caplog, result)


@mock.patch("webbrowser.open", return_value=True, side_effect=None)
def test_init_on_existing_project_with_no_datasources_should_continue_init_flow_and_add_one(
    mock_webbrowser, capsys, caplog, initialized_project,
):
    project_dir = initialized_project
    ge_dir = os.path.join(project_dir, DataContext.GE_DIR)

    # mangle the project to remove all traces of a suite and validations
    _remove_all_datasources(ge_dir)
    os.remove(os.path.join(ge_dir, "expectations", "Titanic", "warning.json"))
    uncommitted_dir = os.path.join(ge_dir, "uncommitted")
    validations_dir = os.path.join(ge_dir, uncommitted_dir, "validations")
    shutil.rmtree(validations_dir)
    os.mkdir(validations_dir)
    shutil.rmtree(os.path.join(uncommitted_dir, "data_docs", "local_site"))
    context = DataContext(ge_dir)
    assert not context.list_expectation_suites()

    csv_path = os.path.join(project_dir, "data", "Titanic.csv")
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli,
        ["init", "-d", project_dir],
        input="1\n1\n{}\nmy_suite\n\n".format(csv_path, catch_exceptions=False),
        catch_exceptions=False,
    )
    assert mock_webbrowser.call_count == 1
    assert "{}/great_expectations/uncommitted/data_docs/local_site/validations/my_suite/".format(project_dir) in mock_webbrowser.call_args[0][0]
    stdout = result.stdout

    assert result.exit_code == 0

    assert "Error: invalid input" not in stdout
    assert "Always know what to expect from your data" in stdout
    assert "What data would you like Great Expectations to connect to" in stdout
    assert "Enter the path (relative or absolute) of a data file" in stdout
    assert "Name the new expectation suite [Titanic.warning]:" in stdout
    assert (
        "Great Expectations will choose a couple of columns and generate expectations"
        in stdout
    )
    assert "A new Expectation suite 'my_suite' was added to your project" in stdout
    assert "Great Expectations is now set up." in stdout

    config = _load_config_file(os.path.join(ge_dir, DataContext.GE_YML))
    assert "files_datasource" in config["datasources"].keys()

    context = DataContext(ge_dir)
    assert context.list_datasources() == [
        {"name": "files_datasource", "class_name": "PandasDatasource"}
    ]
    assert context.list_expectation_suites()[0].expectation_suite_name == "my_suite"
    assert len(context.list_expectation_suites()) == 1

    assert_no_logging_messages_or_tracebacks(caplog, result)


def _remove_all_datasources(ge_dir):
    config_path = os.path.join(ge_dir, DataContext.GE_YML)

    config = _load_config_file(config_path)
    config["datasources"] = {}

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    context = DataContext(ge_dir)
    assert context.list_datasources() == []


def _load_config_file(config_path):
    assert os.path.isfile(config_path), "Config file is missing. Check path"

    with open(config_path, "r") as f:
        read = f.read()
        config = yaml.load(read)

    assert isinstance(config, dict)
    return config


@pytest.fixture
@mock.patch("webbrowser.open", return_value=True, side_effect=None)
def initialized_project(mock_webbrowser, tmp_path_factory):
    """This is an initialized project through the CLI."""
    project_dir = str(tmp_path_factory.mktemp("my_rad_project"))
    os.makedirs(os.path.join(project_dir, "data"))
    data_path = os.path.join(project_dir, "data/Titanic.csv")
    fixture_path = file_relative_path(__file__, "../test_sets/Titanic.csv")
    shutil.copy(fixture_path, data_path)
    runner = CliRunner(mix_stderr=False)
    _ = runner.invoke(
        cli,
        ["init", "-d", project_dir],
        input="Y\n1\n1\n{}\n\n\n\n".format(data_path, catch_exceptions=False),
    )
    assert mock_webbrowser.call_count == 1
    assert "{}/great_expectations/uncommitted/data_docs/local_site/validations/Titanic/warning/".format(project_dir) \
           in mock_webbrowser.call_args[0][0]

    context = DataContext(os.path.join(project_dir, DataContext.GE_DIR))
    assert isinstance(context, DataContext)
    assert len(context.list_datasources()) == 1
    return project_dir


@mock.patch("webbrowser.open", return_value=True, side_effect=None)
def test_init_on_existing_project_with_multiple_datasources_exist_do_nothing(
    mock_webbrowser, caplog, initialized_project, filesystem_csv_2
):
    project_dir = initialized_project
    ge_dir = os.path.join(project_dir, DataContext.GE_DIR)

    context = DataContext(ge_dir)
    context.add_datasource(
        "another_datasource",
        module_name="great_expectations.datasource",
        class_name="PandasDatasource",
    )

    assert len(context.list_datasources()) == 2

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli, ["init", "-d", project_dir], input="n\n", catch_exceptions=False,
    )
    stdout = result.stdout

    assert result.exit_code == 0
    assert mock_webbrowser.call_count == 0
    assert "Error: invalid input" not in stdout

    assert "Always know what to expect from your data" in stdout
    assert "This looks like an existing project that" in stdout
    assert "appears complete" in stdout
    assert "Would you like to build & view this project's Data Docs" in stdout

    assert_no_logging_messages_or_tracebacks(caplog, result)


@mock.patch("webbrowser.open", return_value=True, side_effect=None)
def test_init_on_existing_project_with_datasource_with_existing_suite_offer_to_build_docs_answer_yes(
    mock_webbrowser, caplog, initialized_project,
):
    project_dir = initialized_project

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli, ["init", "-d", project_dir], input="n\n", catch_exceptions=False,
    )
    stdout = result.stdout

    assert result.exit_code == 0
    assert mock_webbrowser.call_count == 0

    assert "Error: invalid input" not in stdout

    assert "Always know what to expect from your data" in stdout
    assert "This looks like an existing project that" in stdout
    assert "appears complete" in stdout
    assert "Would you like to build & view this project's Data Docs" in stdout

    assert_no_logging_messages_or_tracebacks(caplog, result)


@mock.patch("webbrowser.open", return_value=True, side_effect=None)
def test_init_on_existing_project_with_datasource_with_existing_suite_offer_to_build_docs_answer_no(
    mock_webbrowser, caplog, initialized_project,
):
    project_dir = initialized_project

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli, ["init", "-d", project_dir], input="Y\n", catch_exceptions=False,
    )
    stdout = result.stdout

    assert result.exit_code == 0
    assert mock_webbrowser.call_count == 1
    assert "{}/great_expectations/uncommitted/data_docs/local_site/index.html".format(project_dir) in mock_webbrowser.call_args[0][0]

    assert "Error: invalid input" not in stdout

    assert "Always know what to expect from your data" in stdout
    assert "This looks like an existing project that" in stdout
    assert "appears complete" in stdout
    assert "Would you like to build & view this project's Data Docs" in stdout

    assert_no_logging_messages_or_tracebacks(caplog, result)


@mock.patch("webbrowser.open", return_value=True, side_effect=None)
def test_init_on_existing_project_with_datasource_with_no_suite_create_one(
    mock_browser, caplog, initialized_project,
):
    project_dir = initialized_project
    ge_dir = os.path.join(project_dir, DataContext.GE_DIR)
    uncommitted_dir = os.path.join(ge_dir, "uncommitted")

    # mangle the setup to remove all traces of any suite
    expectations_dir = os.path.join(ge_dir, "expectations")
    data_docs_dir = os.path.join(uncommitted_dir, "data_docs")
    validations_dir = os.path.join(uncommitted_dir, "validations")

    _delete_and_recreate_dir(expectations_dir)
    _delete_and_recreate_dir(data_docs_dir)
    _delete_and_recreate_dir(validations_dir)

    context = DataContext(ge_dir)
    assert context.list_expectation_suites() == []

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli,
        ["init", "-d", project_dir],
        input="{}\nsink_me\n\n\n".format(os.path.join(project_dir, "data/Titanic.csv")),
        catch_exceptions=False,
    )
    stdout = result.stdout
    assert result.exit_code == 0
    assert mock_browser.call_count == 1

    assert "Error: invalid input" not in stdout
    assert "Always know what to expect from your data" in stdout
    assert "Enter the path (relative or absolute) of a data file" in stdout
    assert "Generating example Expectation Suite..." in stdout
    assert "The following Data Docs sites were built" in stdout
    assert "Great Expectations is now set up" in stdout
    assert "A new Expectation suite 'sink_me' was added to your project" in stdout

    assert_no_logging_messages_or_tracebacks(caplog, result)


@pytest.mark.xfail(condition=PY2, reason="Py2")
def test_cli_init_on_new_project_with_broken_excel_file_without_trying_again(caplog, tmp_path_factory):
    project_dir = str(tmp_path_factory.mktemp("test_cli_init_diff"))
    os.makedirs(os.path.join(project_dir, "data"))
    data_path = os.path.join(project_dir, "data", "broken_excel_file.xls")
    fixture_path = file_relative_path(__file__, "../test_sets/broken_excel_file.xls")
    shutil.copy(fixture_path, data_path)

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli,
        ["init", "-d", project_dir],
        input="Y\n1\n1\n{}\n\n\nn\n".format(data_path, catch_exceptions=False),
    )
    stdout = result.output

    assert len(stdout) < 3000, "CLI output is unreasonably long."
    assert "Always know what to expect from your data" in stdout
    assert "What data would you like Great Expectations to connect to" in stdout
    assert "What are you processing your files with" in stdout
    assert "Enter the path (relative or absolute) of a data file" in stdout
    assert "Cannot load file." in stdout
    assert "- Please check the file and try again or select a different data file." in stdout
    assert "- Error: Unsupported format, or corrupt file: Expected BOF record; found b'PRODUCTI'" in stdout
    assert "Try again? [Y/n]:" in stdout
    assert "[{}]:".format(data_path) in stdout
    assert "We have saved your setup progress. When you are ready, run great_expectations init to continue." in stdout

    assert os.path.isdir(os.path.join(project_dir, "great_expectations"))
    config_path = os.path.join(project_dir, "great_expectations/great_expectations.yml")
    assert os.path.isfile(config_path)

    config = yaml.load(open(config_path, "r"))
    data_source_class = config["datasources"]["files_datasource"]["data_asset_type"][
        "class_name"
    ]
    assert data_source_class == "PandasDataset"

    assert_no_logging_messages_or_tracebacks(caplog, result)


@pytest.mark.xfail(condition=PY2, reason="Py2")
@mock.patch("webbrowser.open", return_value=True, side_effect=None)
def test_cli_init_on_new_project_with_broken_excel_file_try_again_with_different_file(mock_webbrowser, caplog, tmp_path_factory):
    project_dir = str(tmp_path_factory.mktemp("test_cli_init_diff"))
    os.makedirs(os.path.join(project_dir, "data"))
    data_path = os.path.join(project_dir, "data", "broken_excel_file.xls")
    fixture_path = file_relative_path(__file__, "../test_sets/broken_excel_file.xls")
    data_path_2 = os.path.join(project_dir, "data", "Titanic.csv")
    fixture_path_2 = file_relative_path(__file__, "../test_sets/Titanic.csv")
    shutil.copy(fixture_path, data_path)
    shutil.copy(fixture_path_2, data_path_2)

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli,
        ["init", "-d", project_dir],
        input="Y\n1\n1\n{}\n\n{}\n".format(data_path, data_path_2, catch_exceptions=False),
    )
    stdout = result.output
    assert mock_webbrowser.call_count == 1
    assert "{}/great_expectations/uncommitted/data_docs/local_site/validations/Titanic/warning/".format(project_dir) in \
           mock_webbrowser.call_args[0][0]

    assert len(stdout) < 3000, "CLI output is unreasonably long."
    assert "Always know what to expect from your data" in stdout
    assert "What data would you like Great Expectations to connect to" in stdout
    assert "What are you processing your files with" in stdout
    assert "Enter the path (relative or absolute) of a data file" in stdout
    assert "Cannot load file." in stdout
    assert "- Please check the file and try again or select a different data file." in stdout
    assert "- Error: Unsupported format, or corrupt file: Expected BOF record; found b'PRODUCTI'" in stdout
    assert "Try again? [Y/n]:" in stdout
    assert "[{}]:".format(data_path) in stdout

    assert "Name the new expectation suite [Titanic.warning]" in stdout
    assert (
            "Great Expectations will choose a couple of columns and generate expectations about them"
            in stdout
    )
    assert "Generating example Expectation Suite..." in stdout
    assert "Building" in stdout
    assert "Data Docs" in stdout
    assert "A new Expectation suite 'Titanic.warning' was added to your project" in stdout
    assert "Great Expectations is now set up" in stdout

    assert os.path.isdir(os.path.join(project_dir, "great_expectations"))
    config_path = os.path.join(project_dir, "great_expectations/great_expectations.yml")
    assert os.path.isfile(config_path)

    config = yaml.load(open(config_path, "r"))
    data_source_class = config["datasources"]["files_datasource"]["data_asset_type"][
        "class_name"
    ]
    assert data_source_class == "PandasDataset"

    obs_tree = gen_directory_tree_str(os.path.join(project_dir, "great_expectations"))

    # Instead of monkey patching datetime, just regex out the time directories
    date_safe_obs_tree = re.sub(r"\d*T\d*\.\d*Z", "9999.9999", obs_tree)
    # Instead of monkey patching guids, just regex out the guids
    guid_safe_obs_tree = re.sub(
        r"[a-z0-9]{32}(?=\.(json|html))", "foobarbazguid", date_safe_obs_tree
    )
    assert (
        guid_safe_obs_tree
        == """great_expectations/
    .gitignore
    great_expectations.yml
    expectations/
        Titanic/
            warning.json
    notebooks/
        pandas/
            validation_playground.ipynb
        spark/
            validation_playground.ipynb
        sql/
            validation_playground.ipynb
    plugins/
        custom_data_docs/
            renderers/
            styles/
                data_docs_custom_styles.css
            views/
    uncommitted/
        config_variables.yml
        data_docs/
            local_site/
                index.html
                expectations/
                    Titanic/
                        warning.html
                static/
                    fonts/
                        HKGrotesk/
                            HKGrotesk-Bold.otf
                            HKGrotesk-BoldItalic.otf
                            HKGrotesk-Italic.otf
                            HKGrotesk-Light.otf
                            HKGrotesk-LightItalic.otf
                            HKGrotesk-Medium.otf
                            HKGrotesk-MediumItalic.otf
                            HKGrotesk-Regular.otf
                            HKGrotesk-SemiBold.otf
                            HKGrotesk-SemiBoldItalic.otf
                    images/
                        favicon.ico
                        glossary_scroller.gif
                        iterative-dev-loop.png
                        logo-long-vector.svg
                        logo-long.png
                        short-logo-vector.svg
                        short-logo.png
                        validation_failed_unexpected_values.gif
                    styles/
                        data_docs_custom_styles_template.css
                        data_docs_default_styles.css
                validations/
                    Titanic/
                        warning/
                            9999.9999/
                                foobarbazguid.html
        validations/
            Titanic/
                warning/
                    9999.9999/
                        foobarbazguid.json
""")

    assert_no_logging_messages_or_tracebacks(caplog, result)


def _delete_and_recreate_dir(directory):
    shutil.rmtree(directory)
    assert not os.path.isdir(directory)
    os.mkdir(directory)
    assert os.path.isdir(directory)
