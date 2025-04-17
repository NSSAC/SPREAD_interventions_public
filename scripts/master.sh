#!/bin/bash

function prepare_pipeline_model(){
    prefix="${1:-bd}" # if no arguments given, uses bd_config_model.json
    python3 ../scripts/generate_pipelines_model.py ../input/config_files/${prefix,,}config_model.json
}

function prepare_all_pipelines_model(){
    if [ "$#" -eq 0 ]; then
      myArray=( bd vn ph id th ) # if no arguments given, uses these five networks by default
    else
      myArray=( "$@" )
    fi
    myArray=( "${myArray[@]/#/'../input/config_files/'}" )
    myArray=( "${myArray[@]/%/'config_model.json'}" )
    python3 ../scripts/generate_pipelines_model.py ${myArray[@]}
    # python3 ../scripts/generate_pipelines_model.py ../input/config_files/bdconfig_model.json ../input/config_files/vnconfig_model.json ../input/config_files/phconfig_model.json
}

function prepare_pipeline(){
    prefix="${1:-bd}" # if no arguments given, uses bd_config.json
    python3 ../scripts/generate_pipelines.py ../input/config_files/${prefix,,}config.json
}

function prepare_all_pipelines(){
    if [ "$#" -eq 0 ]; then
      myArray=( bd vn ph id th ) # if no arguments given, uses these five networks by default
    else
      myArray=( "$@" )
    fi
    myArray=( "${myArray[@]/#/'../input/config_files/'}" )
    myArray=( "${myArray[@]/%/'config.json'}" )
    python3 ../scripts/generate_pipelines.py ${myArray[@]}
    # python3 ../scripts/generate_pipelines.py ../input/config_files/bdconfig.json ../input/config_files/vnconfig.json ../input/config_files/phconfig.json
    # multiple commands will overwrite the same file.
}

if [[ $# == 0 ]]; then
   echo "Here are the options:"
   grep "^function" $BASH_SOURCE | sed -e 's/function/  /' -e 's/[(){]//g' -e '/IGNORE/d'
else
   eval $1 $2
fi
