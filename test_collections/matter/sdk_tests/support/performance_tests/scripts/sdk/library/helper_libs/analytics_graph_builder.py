import json
import os
import logging
import shutil

from matter_qa.library.base_test_classes.models.test_results_model import TestExecutionResultsRecordModel

log = logging.getLogger("base_tc")

def build_analytics_json(summary_json: TestExecutionResultsRecordModel):
    analytics_json = {}
    try:
        for analytic in summary_json.test_summary_record.analytics_parameters:
            analytics_json.update({analytic: {}})
        list_iteration_data = summary_json.list_of_iteration_records
        for iteration_data in list_iteration_data:
            analytics_keys = iteration_data.iteration_data.iteration_tc_analytics_data.keys()
            for analytics_key in analytics_keys:
                try:
                    if isinstance(iteration_data.iteration_data.iteration_tc_analytics_data[analytics_key], (int, float)):
                        analytics_json[analytics_key].update(
                            {iteration_data.iteration_number: iteration_data.iteration_data.iteration_tc_analytics_data[analytics_key]})
                    else:
                        analytics_json[analytics_key].update(
                            {iteration_data.iteration_number: None})
                except Exception as e:
                    log.error(e, exc_info=True)
        return analytics_json
    except AttributeError as e:
        raise AttributeError(f'Json File is having some missing Attributes cannot build Graph')
    except Exception as e:
        raise Exception(f'An Exception occurred when tryingto build analytics Json Reason: {str(e)}')

def build_analytics_graph_file(analytics_graph_file_name, summary_json: TestExecutionResultsRecordModel,
                               run_set_folder):
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Path to the HTML file relative to this script
    html_path = os.path.join(script_dir, "analytics_graph_template.html")
    analytics_graph_template_file_fp = open(html_path, "r")
    analytics_graph_template = analytics_graph_template_file_fp.read()
    analytics_graph_template_file_fp.close()
    analytics_json = build_analytics_json(summary_json)
    summary_json_dict_object = summary_json.model_dump(mode="json")
    summary_json_dict_object.update({"analytics": analytics_json})
    summary_json_str = json.dumps(summary_json_dict_object, indent=4)
    updated_graph_template = analytics_graph_template.replace("GraphData", summary_json_str)
    with open(analytics_graph_file_name, "w") as f:
        f.write(updated_graph_template)
    analytics_graph_html_libs_path_source = os.path.join(script_dir, "analytics_graph_html_libs")
    analytics_graph_libs_path_for_runs_set_folder = os.path.join(run_set_folder, "analytics_graph_html_libs")
    shutil.copytree(analytics_graph_html_libs_path_source, analytics_graph_libs_path_for_runs_set_folder,dirs_exist_ok=True)
    return analytics_graph_libs_path_for_runs_set_folder

