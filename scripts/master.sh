#!/bin/bash

HOMEPATH="../scripts"
WORKPATH="../work"
CONFIGFILEPATH="../input/config_files"

function prepare_pipeline_model(){
    create_directories
    prefix="${1:-bd}" # if no arguments given, uses bd_config_model.json
    python3 ${HOMEPATH}/generate_pipelines_model.py ${CONFIGFILEPATH}/${prefix,,}config_model.json
}

function prepare_all_pipelines_model(){
    create_directories
    if [ "$#" -eq 0 ]; then
      myArray=( bd vn ph id th ) # if no arguments given, uses these five networks by default
    else
      myArray=( "$@" )
    fi
    myArray=( "${myArray[@]/#/"${CONFIGFILEPATH}/"}" ) # parameter expansion: adds on end
    myArray=( "${myArray[@]/%/'config_model.json'}" ) # adds at beginning
    python3 ${HOMEPATH}/generate_pipelines_model.py ${myArray[@]}
    # python3 ../scripts/generate_pipelines_model.py ../input/config_files/bdconfig_model.json ../input/config_files/vnconfig_model.json ../input/config_files/phconfig_model.json
}

function prepare_pipeline(){
    create_directories
    prefix="${1:-bd}" # if no arguments given, uses bd_config.json
    python3 ${HOMEPATH}/generate_pipelines.py ${CONFIGFILEPATH}/${prefix,,}config.json
}

function prepare_all_pipelines(){
    create_directories
    if [ "$#" -eq 0 ]; then
      myArray=( bd vn ph id th ) # if no arguments given, uses these five networks by default
    else
      myArray=( "$@" )
    fi
    myArray=( "${myArray[@]/#/"${CONFIGFILEPATH}/"}" )
    myArray=( "${myArray[@]/%/'config.json'}" )
    python3 ${HOMEPATH}/generate_pipelines.py ${myArray[@]}
    # python3 ../scripts/generate_pipelines.py ../input/config_files/bdconfig.json ../input/config_files/vnconfig.json ../input/config_files/phconfig.json
    # multiple commands will overwrite the same file.
}

function create_directories(){
    mkdir -p ${WORKPATH}/configs ${WORKPATH}/sim_summaries ${WORKPATH}/summaries ${WORKPATH}/dags ${WORKPATH}/interventions
    # logs directory will be generated automatically if and when slurm runs
}

if [[ $# == 0 ]]; then
   echo "Here are the options:"
   grep "^function" $BASH_SOURCE | sed -e 's/function/  /' -e 's/[(){]//g' -e '/IGNORE/d'
else
   eval $1 ${@:2}
fi
