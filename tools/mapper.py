from common import definitions, values, utilities
from common.utilities import execute_command, error_exit, get_source_name_from_slice
from tools import emitter, logger, finder, converter, writer, parallel
from ast import ast_generator
import sys

BREAK_LIST = [",", " ", " _", ";", "\n"]


def map_ast_from_source(source_a, source_b, script_file_path):
    logger.trace(__name__ + ":" + sys._getframe().f_code.co_name, locals())
    ast_generator.generate_ast_script(source_a, source_b, script_file_path, True)
    mapping = dict()
    with open(script_file_path, 'r', encoding='utf8', errors="ignore") as script_file:
        script_lines = script_file.readlines()
        for script_line in script_lines:
            if "Match" in script_line:
                node_id_a = int(((script_line.split(" to ")[0]).split("(")[1]).split(")")[0])
                node_id_b = int(((script_line.split(" to ")[1]).split("(")[1]).split(")")[0])
                mapping[node_id_b] = node_id_a
    return mapping


def generate_map_gumtree(file_a, file_b, output_file):
    name_a = file_a.split("/")[-1]
    name_b = file_b.split("/")[-1]
    emitter.normal("\tsource: " + file_a)
    emitter.normal("\ttarget: " + file_b)
    emitter.normal("\tgenerating ast map")
    try:
        extra_arg = ""
        if file_a[-1] == 'h':
            extra_arg = " --"
        generate_command = definitions.DIFF_COMMAND + " -s=" + definitions.DIFF_SIZE + " -dump-matches "
        if values.DONOR_REQUIRE_MACRO:
            generate_command += " " + values.DONOR_PRE_PROCESS_MACRO + " "
            if values.CONF_PATH_B in file_b:
                generate_command += " " + values.DONOR_PRE_PROCESS_MACRO.replace("--extra-arg-a", "--extra-arg-c") + " "
        if values.TARGET_REQUIRE_MACRO:
            if values.CONF_PATH_C in file_b:
                generate_command += " " + values.TARGET_PRE_PROCESS_MACRO + " "
        generate_command += file_a + " " + file_b + extra_arg + " 2> output/errors_clang_diff "
        # command += "| grep '^Match ' "
        generate_command += " > " + output_file
        execute_command(generate_command, False)
    except Exception as e:
        error_exit(e, "Unexpected fail at generating map: " + output_file)


def clean_parse(content, separator):
    if content.count(separator) == 1:
        return content.split(separator)
    i = 0
    while i < len(content):
        if content[i] == "\"":
            i += 1
            while i < len(content) - 1:
                if content[i] == "\\":
                    i += 2
                elif content[i] == "\"":
                    i += 1
                    break
                else:
                    i += 1
            prefix = content[:i]
            rest = content[i:].split(separator)
            node1 = prefix + rest[0]
            node2 = separator.join(rest[1:])
            return [node1, node2]
        i += 1
    # If all the above fails (it shouldn't), hope for some luck:
    nodes = content.split(separator)
    half = len(nodes) // 2
    node1 = separator.join(nodes[:half])
    node2 = separator.join(nodes[half:])
    return [node1, node2]


def generate_map(file_list):

    slice_file_a = file_list[0]
    slice_file_c = file_list[2]
    vector_source_a = get_source_name_from_slice(slice_file_a)
    vector_source_c = get_source_name_from_slice(slice_file_c)
    utilities.shift_slice_source(slice_file_a, slice_file_c)

    ast_tree_a = ast_generator.get_ast_json(vector_source_a, values.DONOR_REQUIRE_MACRO, regenerate=True)
    neighbor_ast = None
    neighbor_ast_range = None
    neighbor_type, neighbor_name, slice = str(slice_file_a).split("/")[-1].split(".c.")[-1].split(".")
    if neighbor_type == "func":
        neighbor_ast = finder.search_function_node_by_name(ast_tree_a, neighbor_name)
    elif neighbor_type == "var":
        neighbor_name = neighbor_name[:neighbor_name.rfind("_")]
        neighbor_ast = finder.search_node(ast_tree_a, "VarDecl", neighbor_name)
    elif neighbor_type == "struct":
        neighbor_ast = finder.search_node(ast_tree_a, "RecordDecl", neighbor_name)

    if neighbor_ast:
        neighbor_ast_range = (int(neighbor_ast['begin']), int(neighbor_ast['end']))
    else:
        utilities.error_exit("No neighbor AST Found")

    map_file_name = definitions.DIRECTORY_OUTPUT + "/" + slice_file_a.split("/")[-1] + ".map"
    if not values.CONF_USE_CACHE:
        generate_map_gumtree(vector_source_a, vector_source_c, map_file_name)

    ast_node_map = parallel.read_mapping(map_file_name)
    # emitter.data(ast_node_map)
    namespace_map = {}
    if values.DEFAULT_OPERATION_MODE == 0 and not values.IS_IDENTICAL:
        ast_node_map = parallel.extend_mapping(ast_node_map, vector_source_a, vector_source_c, int(neighbor_ast['id']))
        # emitter.data(ast_node_map)
        namespace_map = parallel.derive_namespace_map(ast_node_map, vector_source_a,
                                                      vector_source_c, int(neighbor_ast['id']))
    # writer.write_var_map(namespace_map, definitions.FILE_NAMESPACE_MAP_LOCAL)
    utilities.restore_slice_source()

    return ast_node_map, namespace_map


def anti_unification(ast_node_a, ast_node_c):
    au_pairs = dict()
    waiting_list_a = [ast_node_a]
    waiting_list_c = [ast_node_c]

    while len(waiting_list_a) != 0 and len(waiting_list_c) != 0:
        current_a = waiting_list_a.pop()
        current_c = waiting_list_c.pop()

        children_a = current_a["children"]
        children_c = current_c["children"]

        # do not support anti-unification with different number of children yet
        if len(children_a) != len(children_c):
            continue

        length = len(children_a)
        for i in range(length):
            child_a = children_a[i]
            child_c = children_c[i]
            if child_a["type"] == child_c["type"]:
                waiting_list_a.append(child_a)
                waiting_list_c.append(child_c)
            else:
                key = child_a["type"] + "(" + str(child_a["id"]) + ")"
                value = child_c["type"] + "(" + str(child_c["id"]) + ")"
                au_pairs[key] = value

    return au_pairs

