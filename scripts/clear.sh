#!/bin/bash
# A simple shell script to clear out work files for the SI pipeline.

WORKPATH="../work"
# Where files are saved:
CONFIG_PATH="${WORKPATH}/configs"
SIM_SUMMARY_PATH="${WORKPATH}/sim_summaries"
DAG_PATH="${WORKPATH}/dags"
SUMMARY_PATH="${WORKPATH}/summaries"
INTERVENTION_PATH="${WORKPATH}/interventions"
LOG_PATH="${WORKPATH}/logs"

set -e # exit on any error
shopt -s nullglob # no match wildcard --> null string

NAME=$0
display_usage(){
    echo "Usage: $NAME [-c] [-s] [-i] [-l]"
    echo "Clears specified directory of files"
    echo "Include -c to delete config files, -s to delete dag files, -i to delete intervention output, and/or -l to delete logs."
    echo "By default, deletes everything"
    exit 0
}

while getopts ":csil" opt; do
    case $opt in
        c)
            config=1
            ;;
        s)
            simulator=1 # mark so not empty string
            ;;
        i)
            intervention=1
            ;;
        l)
            logs=1
            ;;
        ?) 
            display_usage
            ;;
    esac
done

if [[ -z "$config" && -z "$simulator" && -z "$intervention" && -z "$logs" ]]; then
        config=2; simulator=2; intervention=2; logs=2
fi
if [ -n "$config" ]; then
    echo "Deleting config files..."
    # clear out CONFIG_PATH folder
    if [ -n "$(echo ${CONFIG_PATH}/*.json)" ]; then
        rm ${CONFIG_PATH}/*.json
    fi
fi
if [ -n "$simulator" ]; then
    echo "Deleting DAG files..."
    # clear out DAG_PATH folder
    if [ -n "$(echo ${DAG_PATH}/*.csv)" ]; then
        rm ${DAG_PATH}/*.csv
    fi
    echo "Deleting simulation summaries..."
    # clear out SIM_SUMMARY_PATH folder
    if [ -n "$(echo ${SIM_SUMMARY_PATH}/*.csv)" ]; then
        rm ${SIM_SUMMARY_PATH}/*.csv
    fi

fi
if [ -n "$intervention" ]; then
    echo "Deleting intervention output..."
    if [ -n "$(echo ${INTERVENTION_PATH}/*)" ]; then
        rm -rf ${INTERVENTION_PATH}/*
    fi
    if [ -n "$(echo ${SUMMARY_PATH}/*.csv)" ]; then
        rm ${SUMMARY_PATH}/*.csv
    fi
fi
if [ -n "$logs" ]; then
    echo "Deleting logs..."
    if [ -n "$(echo ${LOG_PATH}/*.txt)" ]; then
        rm ${LOG_PATH}/*.txt
    fi
    if [ -n "$(echo ${LOG_PATH}/*)" ]; then
        #folders
        rm -rf ${LOG_PATH}/*
    fi

fi

