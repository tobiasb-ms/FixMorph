#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 12 10:25:58 2018

@author: pedrobw
"""

import os
import time
from Utils import exec_com, err_exit, find_files, remove_Hexa, clean, \
                  get_extensions
import Project
import ASTVector
import Print

Pa = None
Pb = None
Pc = None


''' Main vector generation functions '''


def gen_AST(file, src_dir):
    
    # Check that we have an appropriate file
    if not os.path.isfile(file):
        err_exit("This is not a file: \n" + file)
        
    # Uses clang -ast-dump to generate an AST for file an saves it in "AST"
    c = "clang -Xclang -ast-dump -fsyntax-only -fno-diagnostics-color " + \
        "-ferror-limit=0 -w -I /usr/include/ -I /usr/local/include/ "
    
    # We try to include any .h file stated in the .c file
    d = "cat " + file + " | grep '#include ' | grep '\.h' > output/hs"
    exec_com(d, False)
    includes = set()
    with open('output/hs', 'r', errors='replace') as h_files:
        line = h_files.readline().strip()
        while line:
            # For cases of the form '#include "****.h"'
            if '"' in line:
                line = line.split('"')[1]
            # For cases of the form '#include <****.h>'
            else:
                line = line.split('<')[1].split('>')[0]
            # We only keep the file name or find doesn't work
            line = line.split("/")[-1]
            c1 = "find " + src_dir + " -name '" + line + "'"
            l = exec_com(c1, False)[0].split("\n")
            for i in l:
                i = i.split("/")
                if len(i) > 2:
                    # Here we get the directory and the parent directory
                    includes.add("/".join(i[:-1]))
                    includes.add("/".join(i[:-2]))
            line = h_files.readline().strip()
    for include in includes:
        c += "-I " + include + " "
    c += file + " > " + file + ".AST 2>> output/errors"
    try:
        exec_com(c, False)
    except Exception as e:
        err_exit(e, "Error with clang AST dump on file:", file,
                 "Reproduce with command:", c.replace("2>> errors", ""),
                 "or look at file 'errors'.")


def gen_vec(project_attribute, file, func_or_struct, start, end, Deckard=True):
    v = ASTVector.ASTVector(file, func_or_struct, start, end, Deckard)
    if not v.vector:
        return None
    if file in project_attribute.keys():
        project_attribute[file][func_or_struct] = v
    else:
        project_attribute[file] = dict()
        project_attribute[file][func_or_struct] = v
    return v


def parseAST(filepath, proj, Deckard=True):
    try:
        gen_AST(filepath, proj.path)
        # Path to the AST file generated by gen_AST
        AST = filepath + ".AST"
    except Exception as e:
        err_exit(e, "Unexpected error in gen_AST with file:", filepath)
    # Keep functions here
    function_lines = []
    # Keep structures here
    structure_lines = []
    # Keep variables for each function d[function] = "typevar namevar; ...;"
    dict_file = dict()
    # If we're inside the tree parsing a function
    in_function = False
    # If we're inside the tree parsing a struct
    in_struct = False
    # Start and ending line of the function/struct
    start = 0
    end = 0
    
    file = filepath.split("/")[-1]
    
    if Deckard:
        Print.grey("Generating vectors for " + filepath.split("/")[-1])
    
    
    with open(AST, 'r', errors='replace') as f:
        # A line is a node of the AST
        line = f.readline().strip()
        # Skip irrelevant things from other files
        while line:
            if filepath in line and ".c" not in line.replace(file, ""):
                break
            line = f.readline().strip()
        # We find Function declarations and retrieve parameters and variables
        while line:
            # Skip irrelevant things from other files
            if ".h" in line or ".c" in line.replace(file, ""):
                in_function = False
                in_struct = False
                while line:
                    if filepath in line and ".c" not in line.replace(file, ""):
                        break
                    line = f.readline().strip()
            # Function declaration: Capture start, end and use Deckard on it
            elif (("-FunctionDecl " in line) and ("col:" not in line) and 
                "invalid sloc" not in line):
                in_struct = False
                line = line.split(" ")
                if line[-1] != "extern":
                    line = remove_Hexa(line)
                    # col: appears for .h files and other references
                    lines_aux = line.split("> ")
                    lines = lines_aux[0].split(" <")[1]
                    if "invalid" not in lines:
                        try:
                            start = lines_aux[1].split(":")[1]
                            end = lines.split(", ")[1]
                            end = end.split(":")[1]
                            f = line.split(" '")[-2].split(" ")[-1]
                        except Exception as e:
                            err_exit(e, ":(")
                        in_function = True
                        try:
                            start = int(start)
                            end = int(end)
                        except Exception as e:
                            err_exit("Parsing error, not ints.", start, end, 
                                     line, lines_aux, lines, e)
                        function_lines.append((f, start, end))
                        gen_vec(proj.funcs, filepath, f, start, end, Deckard)
                    else:
                        in_function = False
                else:
                    in_function = False
            # Capture variable in function
            elif in_function and ("VarDecl " in line) and \
                 ("invalid sloc" not in line):
                in_struct = False
                line = "-".join(line.split("-")[1:]).split(" ")
                line = remove_Hexa(line).split(" '")
                # TODO: Get variable types
                var_type = " '".join(line[1:]).split("'")[0]
                line = line[0].split(" ")
                line = line[0].replace("Decl", "") + " " + line[-1]
                line = line.replace("  ", "").split(" ")
                line = line[0] + " " + var_type + " " + line[1] + ";"
                if f not in dict_file.keys():
                    dict_file[f] = ""
                dict_file[f] = dict_file[f] + line
                
            # FIXME: This also accounts for struct declarations inside function
            '''
            elif ("-RecordDecl " in line) and ("struct" in line):
                in_function = False
                line = line.split(" ")
                line = remove_Hexa(line)
                if "invalid sloc" not in line and "scratch space" not in line:
                    in_struct = True
                    try:
                        lines = line.split("> ")[0].split(" <")[1].split(",")
                        start = lines[0].split(":")[1]
                        end = lines[1].split(":")[1]
                    except:
                        err_exit(line, lines, "RecordDecl error")
            elif in_struct and ("-FieldDecl" in line):
                if False:
                    Print.green("\t" + line)
            elif in_struct and ("-TypedefDecl" in line):
                try:
                    if len(line) > 2 and start and end:
                        struct = line.split(" '")[-2].split(" ")[-1]
                        structure_lines.append((struct, int(start), int(end)))
                        gen_vec(proj.structs, filepath, struct, start, end,
                                False)
                except Exception as e:
                    err_exit(e)
                in_struct = False
            '''
            line = f.readline().strip()
    
    with open('output/function-lines', 'w') as func_l:
        for l in function_lines:
            func_l.write(l[0] + " " + str(l[1]) + "-" + str(l[2]) + "\n")
    with open('output/function-vars', 'w') as func_l:
        for func in dict_file.keys():
            func_l.write(func + "\n")
            for line in dict_file[func].split(";"):
                func_l.write("\t" + line.replace("  ", "") + "\n")
    if Deckard:
        get_vars(proj, filepath, dict_file)
    return function_lines, dict_file


def get_vars(proj, file, dict_file):
    for func in dict_file.keys():
        for line in dict_file[func].split(";"):
            if file in proj.funcs.keys():
                if func in proj.funcs[file].keys():
                    if "ParmVar" in line:
                        line = line.replace("  ", "").replace("ParmVar ", "")
                        proj.funcs[file][func].params.append(line)
                    else:
                        line = line.replace("  ", "").replace("Var ", "")
                        proj.funcs[file][func].variables.append(line)
                        
    
def gen_ASTs():
    # Generates an AST file for each .c file
    find_files(Pc.path, "*.c", "output/Cfiles")
    with open("output/Cfiles", 'r', errors='replace') as files:
        file = files.readline().strip()
        while file:
            # Parses it to remove useless information (for us) and gen vects
            try:
                parseAST(file, Pc)
            except Exception as e:
                err_exit(e, "Unexpected error in parseAST with file:", file)
            file = files.readline().strip()


def intersect(start, end, start2, end2):
    return not (end2 < start or start2 > end)


def find_diff_files():
    global Pa, Pb
    extensions = get_extensions(Pa.path, "output/files1")
    extensions = extensions.union(get_extensions(Pb.path, "output/files2"))
    with open('output/exclude_pats', 'w', errors='replace') as exclusions:
        for pattern in extensions:
            exclusions.write(pattern + "\n")
    c = "diff -ENBbwqr " + Pa.path + " " + Pb.path + \
        " -X output/exclude_pats | grep -P '\.c and ' " + \
        "> output/diff"
    exec_com(c, False)


def find_affected_funcs(proj, file, pertinent_lines):
    try:
        function_lines, dict_file = parseAST(file, proj, False)
    except Exception as e:
        err_exit(e, "Error in parseAST.")
    for start2, end2 in pertinent_lines:
        for f, start, end in function_lines:
            if intersect(start, end, start2, end2):
                if file not in proj.funcs.keys():
                    proj.funcs[file] = dict()
                if f not in proj.funcs[file]:
                    proj.funcs[file][f] = ASTVector.ASTVector(file, f, start,
                                                              end, True)
                    Print.rose("\t\tFunction successfully found in " + \
                               file.split("/")[-1])
                    Print.grey("\t\t\t" + f + " " + str(start) + "-" + \
                               str(end), False)
                break
    get_vars(proj, file, dict_file)
    return function_lines, dict_file
    
    
def gen_diff():
    global Pa, Pb
    nums = "0123456789"
    Print.blue("Finding differing files...")
    find_diff_files()
    
    Print.blue("Starting fine-grained diff...\n")
    with open('output/diff', 'r', errors='replace') as diff:
        diff_line = diff.readline().strip()
        while diff_line:
            diff_line = diff_line.split(" ")
            file_a = diff_line[1]
            file_b = diff_line[3]
            c = "diff -ENBbwr " + file_a + " " + file_b + " > output/file_diff"
            exec_com(c, False)
            pertinent_lines = []
            pertinent_lines_b = []
            with open('output/file_diff', 'r', errors='replace') as file_diff:
                file_line = file_diff.readline().strip()
                while file_line:
                    # In file_diff, line starts with a number, <, >, or -.
                    if file_line[0] in nums:
                        # change (delete + add)
                        if 'c' in file_line:
                            l = file_line.split('c')
                        elif 'd' in file_line:
                            l = file_line.split('d')
                        elif 'a' in file_line:
                            l = file_line.split('a')
                        # range for file_a
                        a = l[0].split(',')
                        start_a = int(a[0])
                        end_a = int(a[-1])
                        # range for file_b
                        b = l[1].split(',')
                        start_b = int(b[0])
                        end_b = int(b[-1])
                        # Pertinent lines in file_a
                        pertinent_lines.append((start_a, end_a))
                        pertinent_lines_b.append((start_b, end_b))
                    file_line = file_diff.readline().strip()
            try:
                Print.blue("\tProject Pa...")
                find_affected_funcs(Pa, file_a, pertinent_lines)
                Print.blue("")
                Print.blue("\tProject Pb...")
                find_affected_funcs(Pb, file_b, pertinent_lines)
            except Exception as e:
                err_exit(e, "HERE")
                        
            diff_line = diff.readline().strip()

    
def norm(v):
    return sum(v[i]**2 for i in range(len(v)))**(1/2)    


def normed(v):
    n = norm(v)
    return [i/n for i in v]
    

def dist(u, v):
    assert(len(u)==len(v))
    return sum(((u[i] - v[i])**2) for i in range(len(u)))

    
def get_vector_list(src_path, filepath):
    find_files(src_path, "*.vec", filepath)
    with open(filepath, "r", errors='replace') as file:
        files = [vec.strip() for vec in file.readlines()]
    vecs = []
    for i in range(len(files)):
        with open(files[i], 'r', errors='replace') as vec:
            fl = vec.readline()
            if fl:
                v = [int(s) for s in vec.readline().strip().split(" ")]
                v = normed(v)
                vecs.append((files[i],v))
    return vecs
                
    
def compare():
    global Pa, Pc
    Print.blue("Getting vectors for Pa...")
    vecs_A = get_vector_list(Pa.path, "output/output_A")
    Print.blue("Getting vectors for Pc...")
    vecs_C = get_vector_list(Pc.path, "output/output_C")
    
    Print.blue("Variable mapping...\n")
    to_patch = []
    for i in vecs_A:
        best = vecs_C[0]
        best_d = dist(i[1], best[1])
        for j in vecs_C:
            d = dist(i[1],j[1])
            if d < best_d:
                best = j
                best_d = d
        # We go up to -4 to remove the ".vec" part
        fa = i[0].replace(Pa.path, "")[:-4].split(".")
        f_a = fa[-1]
        file_a = ".".join(fa[:-1])
        fc = best[0].replace(Pc.path, "")[:-4].split(".")
        f_c = fc[-1]
        file_c = ".".join(fc[:-1])
        # TODO: Get all pertinent matches (at dist d' < k*best_d)
        Print.blue("\tBest match for " + f_a +" in $Pa/" + file_a + ":")
        Print.blue("\t\tFunction: " + f_c + " in $Pc/" + file_c)
        Print.blue("\t\tDistance: " + str(best_d) + "\n")
        Print.blue("\tVariable mapping from " + f_a + " to " + f_c + ":")
        try:
            var_map = detect_matching_variables(f_a, file_a, f_c, file_c)
        except Exception as e:
            err_exit(e, "Unexpected error while matching variables.")
        with open('output/var-map', 'r', errors='replace') as mapped:
            mapping = mapped.readline().strip()
            while mapping:
                Print.grey("\t\t" + mapping)
                mapping = mapped.readline().strip()
        to_patch.append((Pa.funcs[Pa.path + file_a][f_a],
                         Pc.funcs[Pc.path + file_c][f_c], var_map))
    return to_patch
    
def path_exception():
    m = "ValueError Exception: Incorrect directory path"
    return ValueError(m)    
    
    
def longestSubstringFinder(string1, string2):
    answer = ""
    maxlen = min(len(string1), len(string2))
    i = 0
    while i < maxlen:
        if string1[i] != string2[i]:
            break
        answer += string1[i]
        i += 1
    return answer
    
def generate_ast_map(source_a, source_b):
    common_path = longestSubstringFinder(source_a, source_b).split("/")[:-1]
    common_path = "/".join(common_path)
    ast_diff_command = "gumtree diff " + source_a + " " + source_b + \
                        " | grep -P 'Match GenericString: [A-Za-z0-9_]*\('" + \
                        " > output/ast-map "
    exec_com(ast_diff_command, False)
    

def detect_matching_variables(f_a, file_a, f_c, file_c):
    
    try:
        generate_ast_map(Pa.path + "/" + file_a, Pc.path + "/" + file_c)
    except Exception as e:
        err_exit(e, "Unexpected error in generate_ast_map.")
    function_a = Pa.funcs[Pa.path + file_a][f_a]
    variable_list_a = function_a.variables + function_a.params
    Print.white(variable_list_a)
    while '' in variable_list_a:
        variable_list_a.remove('')
        
    a_names = [i.split(" ")[-1] for i in variable_list_a]
        
    function_c = Pc.funcs[Pc.path + file_c][f_c]
    variable_list_c = function_c.variables + function_c.params
    #Print.white(variable_list_c)
    while '' in variable_list_c:
        variable_list_c.remove('')
    
    ast_map = dict()
    try:
        with open("output/ast-map", "r", errors='replace') as ast_map_file:
            map_line = ast_map_file.readline().strip()
            while map_line:
                aux = map_line.split(" to ")
                var_a = aux[0].split("(")[0].split(" ")[-1]
                var_c = aux[1].split("(")[0].split(" ")[-1]
                if var_a in a_names:
                    if var_a not in ast_map:
                        ast_map[var_a] = dict()
                    if var_c in ast_map[var_a]:
                        ast_map[var_a][var_c] += 1
                    else:
                        ast_map[var_a][var_c] = 1
                map_line = ast_map_file.readline().strip()
    except Exception as e:
        err_exit(e, "Unexpected error while parsing ast-map")

    variable_mapping = dict()
    try:
        while variable_list_a:
            var_a = variable_list_a.pop()
            if var_a not in variable_mapping.keys():
                a_name = var_a.split(" ")[-1]
                if a_name in ast_map.keys():
                    max_match = -1
                    best_match = None
                    for var_c in ast_map[a_name].keys():
                        if max_match == -1:
                            max_match = ast_map[a_name][var_c]
                            best_match = var_c
                        elif ast_map[a_name][var_c] > max_match:
                            max_match = ast_map[a_name][var_c]
                            best_match = var_c
                    if best_match:
                        for var_c in variable_list_c:
                            c_name = var_c.split(" ")[-1]
                            if c_name == best_match:
                                variable_mapping[var_a] = var_c
                if var_a not in variable_mapping.keys():
                    variable_mapping[var_a] = "UNKNOWN"
    except Exception as e:
        err_exit(e, "Unexpected error while matching vars.")

    try:
        with open("output/var-map", "w", errors='replace') as var_map_file:
            for var_a in variable_mapping.keys():
                var_map_file.write(var_a + " -> " + variable_mapping[var_a] + \
                                   "\n")
    except Exception as e:
        err_exit(e, "ASdasdas")
    
    return variable_mapping
    

def gen_func_file(ast_vec_func, output_file):
    start = ast_vec_func.start
    end = ast_vec_func.end
    Print.blue("\t\tStart line: " + str(start))
    Print.blue("\t\tEnd line: " + str(end))
    
    with open(output_file, 'w') as temp:
        with open(ast_vec_func.file, 'r', errors='replace') as file:
            ls = file.readlines()
            while start > 0:
                j = start-1
                if "}" in ls[j] or "#include" in ls [j] or ";" in ls[j] or "*/" in ls[j]:
                    break
                start = j
            temp.write("".join(ls[start:end]))


def transplantation(to_patch):
    
    for (ast_vec_f_a, ast_vec_f_c,var_map) in to_patch:
        
        ast_vec_f_b = Pb.funcs[ast_vec_f_a.file.replace(Pa.path, Pb.path)][ast_vec_f_a.function]
        
        Print.blue("Generating temp files for each pertinent function...")
        Print.blue("\tFunction " + ast_vec_f_a.function + " in Pa...")
        gen_func_file(ast_vec_f_a, "output/temp_a.c")
        Print.blue("\tFunction " + ast_vec_f_b.function + " in Pb...")
        gen_func_file(ast_vec_f_b, "output/temp_b.c")
        Print.blue("\tFunction " + ast_vec_f_c.function + " in Pc...")
        gen_func_file(ast_vec_f_c, "output/temp_c.c")
        
        Print.blue("Generating edit script from Pa to Pb...")
        exec_com("gumtree diff output/temp_a.c output/temp_b.c " + \
                 "> output/diff_script_AB", False)
                 
        Print.blue("Finding common structures in Pa with respect to Pc...")
        exec_com("gumtree diff output/temp_a.c output/temp_c.c | " + \
                 "grep 'Match ' > output/diff_script_AC", False)
        
        UPDATE = "Update"
        MOVE = "Move"
        INSERT = "Insert"
        DELETE = "Delete"
        MATCH = "Match"
        MATCHED = "Matched"
        TO = " to "
        AT = " at "
        INTO = " into "
        
        diffs = dict()
        diffs[UPDATE] = dict()
        diffs[MOVE] = dict()
        diffs[INSERT] = dict()
        diffs[DELETE] = list()
        diffs[MATCH] = dict()
        diffs[MATCHED] = dict()
        
        with open('output/diff_script_AB', 'r') as script_AB:
            line = script_AB.readline().strip()
            while line:
                line = line.split(" ")
                instruction = line[0]
                line = " ".join(line[1:])
                if instruction == UPDATE:
                    # Update node1 to node2
                    line = line.split(TO)
                    diffs[UPDATE][line[0]] = line[1]
                elif instruction == MOVE:
                    # Move node1 into node2 at pos
                    line.split(INTO)
                    diffs[MOVE][line[0]] = line[1].split(AT)
                elif instruction == INSERT:
                    # Insert node1 into node2 at pos
                    line.split(INTO)
                    diffs[MOVE][line[0]] = line[1].split(AT)
                elif instruction == DELETE:
                    # Delete node
                    diffs[DELETE].append(line)
                elif instruction == MATCH:
                    # Match node1 to node2
                    line = line.split(TO)
                    diffs[MATCH][line[0]] = line[1]
                    # We keep track of what is node1 for node2
                    diffs[MATCHED][line[1]] = line[0]
                line = script_AB.readline().strip()
                
        common = dict()
        common[UPDATE] = dict()
        common[MOVE] = dict()
        common[INSERT] = dict()
        common[DELETE] = list()
        common[MATCH] = dict()
        
        with open('output/diff_script_AC', 'r') as script_AC:
            line = script_AC.readline().strip()
            while line:
                line = line[6:].split(TO)
                common[MATCH][line[0]] = line[1]
                line = script_AC.readline().strip()
        
        for nodeA in common[MATCH].keys():
            nodeC = common[MATCH][nodeA]
            try:
                # Case DELETE: nodeA is deleted and nodeC matches nodeA
                if nodeA in diffs[DELETE]:
                    common[DELETE].append(nodeC)
            except Exception as e:
                err_exit(e, "Something went wrong in DELETE matching.")
            
            try:                    
                # Case MOVE: nodeA is moved to nodeB, nodeC matches nodeA
                if nodeA in diffs[MOVE].keys():
                    nodeB, pos = diffs[MOVE][nodeA]
                    # TODO: Do something with pos!!!
                    if nodeB in diffs[MATCHED].keys():
                        nodeA2 = diffs[MATCHED][nodeB]
                        # 1st: nodeB matches some nodeA' matching some nodeC'
                        if nodeA2 in common[MATCH].keys():
                            nodeD = common[MATCH][nodeA2]
                            common[MOVE][nodeC] = [nodeD, pos]
                        # 2nd: nodeB matches some nodeA', but we have no match
                        else:
                            common[MOVE][nodeC] = [nodeB, pos]
                            # TODO: Should we do more?
                            # E.g. include anything connected to that node
                            
                    # 3rd: nodeB doesn't have anything alike
                    else:
                        common[MOVE][nodeC] = [nodeB, pos]
            except Exception as e:
                err_exit(e, "Something went wrong in MOVE matching.")
            try:       
                # Case INSERT: nodeA inserted into nodeB, nodeC matches nodeA
                if nodeA in diffs[INSERT].keys():
                    nodeB, pos = diffs[INSERT][nodeA]
                    #TODO: Something with pos!
                    if nodeB in diffs[MATCHED].keys():
                        nodeA2 = diffs[MATCHED][nodeB]
                        # 1st: nodeB matches some nodeA2 matching some nodeD
                        if nodeA2 in common[MATCH].keys():
                            nodeD = common[MATCH][nodeA2]
                            common[INSERT][nodeC] = [nodeD, pos]
                        # 2nd: nodeB matches some nodeA2, no match for nodeA2
                        else:
                            common[INSERT][nodeC] = [nodeB, pos]
                            # TODO: Should we do more?
                            # E.g. include anything connected to that node
                            
                    # 3rd: nodeB doesn't have anything alike
                    else:
                        common[INSERT][nodeC] = [nodeB, pos]
            except Exception as e:
                err_exit(e, "Something went wrong in INSERT matching.")
            try:    
                # Case UPDATE: nodeA is updated to nodeB, nodeC matches nodeA
                if nodeA in diffs[UPDATE].keys():
                    nodeB = diffs[UPDATE][nodeA]
                    if nodeB in diffs[MATCHED].keys():
                        nodeA2 = diffs[MATCHED][nodeB]
                        # 1st: nodeB matches some nodeA2 matching some nodeD
                        if nodeA2 in common[MATCH].keys():
                            nodeD = common[MATCH][nodeA2]
                            common[UPDATE][nodeC] = nodeD
                        # 2nd: nodeB matches some nodeA2, but match for nodeA2
                        else:
                            common[UPDATE][nodeC] = nodeB
                            # TODO: Should we do more?
                            # E.g. include anything connected to that node
                            
                    # 3rd: nodeB doesn't have anything alike in Pc
                    else:
                        common[INSERT][nodeC] = nodeB
            except Exception as e:
                err_exit(e, "Something went wrong in UPDATE matching.")
        for key in common.keys():
            if key == UPDATE:
                Print.white(key)
                for i in common[key].keys():
                    Print.white("\t" + i + " to " + common[key][i])
            elif key == DELETE:
                Print.white(key)
                for i in common[key]:
                    Print.white("\t" + i)
            elif key != MATCH:
                Print.white(key)
                for i in common[key].keys():
                    Print.white("\t" + i + " into " + common[key][i])
                    
def run_crochet():
    global Pa, Pb, Pc
    # Little crochet introduction
    Print.start()
    
    # Time for final running time
    start = time.time()
    
    # Prepare projects directories by getting paths and cleaning residual files
    Print.title("Preparing projects...")
    with open('crochet.conf', 'r', errors='replace') as file:
        args = [i.strip() for i in file.readlines()]
    if (len(args) < 3):
        err_exit("Insufficient arguments: Pa, Pb, Pc source paths required.",
                 "Try running:", "\tpython3 ASTcrochet.py $Pa $Pb $Pc")
    Pa = Project.Project(args[0], "Pa")
    Pb = Project.Project(args[1], "Pb")
    Pc = Project.Project(args[2], "Pc")
    clean()
    Print.rose("Successful cleaning, after " + str(time.time() - start) + \
               " seconds.")
    # Generates vectors for pertinent functions (modified from Pa to Pb)
    Print.title("Getting modified functions in Pa and generating vectors...")   
    try:
        gen_diff()
        Print.rose("Functions successfully found, after " + \
                    str(time.time() - start) + " seconds.")
    except Exception as e:
        err_exit(e, "Unexpected error while finding relevant functions.")
    
    # Generates vectors for all functions in Pc
    Print.title("Generating vectors for functions in Pc...")
    try:
        gen_ASTs()
        Print.rose("Vectors for Pc successfully generated, after " + \
                    str(time.time() - start) + " seconds.")
    except Exception as e:
        err_exit(e, "Unexpected error while generating vectors.")

    # Pairwise vector comparison for matching
    Print.title("Starting pairwise vector comparison for matching...")
    try:
        to_patch = compare()
        Print.rose("Successful comparison, after " + \
                    str(time.time() - start) + " seconds.")
    except Exception as e:
        err_exit(e, "Unexpected error while doing pairwise comparison.")
    
    # Using all previous structures to transplant patch
    Print.title("Starting patch transplantation...")
    try:
        transplantation(to_patch)
        Print.rose("Successful patch proposal, after " + \
                    str(time.time() - start) + " seconds.")
    except Exception as e:
        err_exit(e, "Unexpected error in transplantation algorithm.")
    # TODO: Transplant patch
    
    # Final clean
    Print.title("Cleaning residual files generated by Crochet...")
    
    # Final running time and exit message
    end = time.time()
    Print.exit_msg(start, end)
    
    
if __name__=="__main__":
    #test_parsing()
    try:
        run_crochet()
    except KeyboardInterrupt as e:
        err_exit("Program Interrupted by User")