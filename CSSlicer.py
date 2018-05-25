import cs
import os, signal
import sys
import json
import operator

project = ''
proj_dir = ''

function_info = dict()
output_dir = 'crochet-output/'


def initialize_project():
    global project, proj_dir
    project = cs.project.current()
    proj_dir = sys.argv[1]
    return


def get_function_details():
    for func in project.procedures():
        function_name = func.name()
        if '#' in function_name:
            continue
        try:
            source_file = func.file_line()
            source_file_path = source_file[0].name()
            if source_file_path not in function_info:
                function_info[source_file_path] = dict()

            function_info[source_file_path][function_name] = dict()
            function_info[source_file_path][function_name]['variable-list'] = get_variable_list(func)
            function_info[source_file_path][function_name]['line-range'] = get_function_lines(func)

        except Exception as e:
            print "exception processing function ", function_name
            print(e)
            continue


def output_slice_file(file_name, function_name, variable_name, line_list):
    output_path = output_dir + "/" + file_name + "-" + function_name + "-" + variable_name
    with open(output_path, 'w') as slice_file:
        for line in line_list:
            slice_file.write("%s\n", line)


def get_variable_slice(point_list, variable):
    #print "slicing"
    sorted_sliced_lines = list()
    #print variable.name()
    if '$return' in variable.name():
        return list()

    filter_point_types = ["global-actual-in", "global-actual-out",
                          "global-formal-in", "global-formal-out",
                          "in", "out", "auxiliary"]


    declarations = variable.declarations()
    # print "got declarations"
    sliced_lines = dict()
    chopped_points = declarations.chop(point_list)
    chopped_points = chopped_points.intersect(point_list)
    # print chopped_points
    if chopped_points:
        #print "got chopped"
        for point in chopped_points:
            if hasattr(point, 'get_kind'):
                #print point
                if str(point.get_kind()) not in filter_point_types:
                    statement = point.__str__()
                    if '$result' not in statement and '$return' not in statement:
                        line_number = point.compunit_line()[1]
                        sliced_lines[line_number] = statement
    #print "sorting"
    sorted_sliced_lines = sorted(sliced_lines.items(), key=operator.itemgetter(0))
    #print "sorted"
    return list(sorted_sliced_lines)


def get_variable_list(procedure):
    symbol_list = list(procedure.local_symbols())
    var_list = dict()
    source_file_name = procedure.file_line()[0].name()

    for var in symbol_list:
        var_info = dict()
        var_name = var.name().split("-")[0]

        var_info['type'] = var.get_type().get_class().name()
        declaration_lines = get_variable_line_number_list(var.declarations(), source_file_name)
        var_info['dec-line-numbers'] = declaration_lines

        used_lines = get_variable_line_number_list(list(var.used_points()), source_file_name)
        var_info['use-line-numbers'] = used_lines

        successive_lines = get_variable_line_number_list(list(var.used_points()), source_file_name)
        killed_lines = get_variable_line_number_list(list(var.killed_points()) + list(var.may_killed_points()),
                                                     source_file_name)
        var_info['killed-line-numbers'] = killed_lines

        # slice_lines = get_variable_slice(procedure.points(), var)
        # var_info['sliced-lines'] = slice_lines

        var_list[var_name] = var_info
    return var_list


def run():
    initialize_project()
    create_output_directories()
    get_function_details()
    print_function_info()
    # kill_csruf_shell()
    exit(0)


run()
