#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import time
import Initialization
import Detection
import Extraction
import Mapping
import Translation
import Weaver
from Utils import err_exit
import Print


def run_patchweave():

    Print.start()
    start_time = time.time()
    
    # Prepare projects directories by getting paths and cleaning residual files
    initialization_start_time = time.time()
    Initialization.initialize()
    initialization_duration = str(time.time() - initialization_start_time)

    function_identification_start_time = time.time()
    Detection.detect()
    function_identification_duration = str(time.time() - function_identification_start_time)

    patch_extraction_start_time = time.time()
    Extraction.extract()
    patch_extraction_duration = str(time.time() - patch_extraction_start_time)

    mapping_start_time = time.time()
    Mapping.map()
    mapping_duration = str(time.time() - mapping_start_time)

    translation_start_time = time.time()
    Translation.translate()
    translation_duration = str(time.time() - translation_start_time)

    transplantation_start_time = time.time()
    Weaver.weave()
    transplantation_duration = str(time.time() - transplantation_start_time)

    # Final clean
    Print.title("Cleaning residual files generated by Crochet...")
    
    # Final running time and exit message
    run_time = str(time.time() - start_time)
    Print.exit_msg(run_time, initialization_duration, function_identification_duration, patch_extraction_duration, translation_duration, transplantation_duration)
    
    
if __name__ == "__main__":
    try:
        run_patchweave()
    except KeyboardInterrupt as e:
        err_exit("Program Interrupted by User")
