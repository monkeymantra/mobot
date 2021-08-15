#!/usr/bin/env bash

echo "Running pre-commit hook"
COPYRIGHT_TEXT="# Copyright (c) 2021 MobileCoin. All rights reserved."

git diff --cached --name-status | while read flag file; do
    if [ "$flag" == 'D' ]; then continue; fi
      if [[  ! $(head -1 $file | grep $COPYRIGHT_TEXT) ]]; then
          echo "ERROR: Mising MobileCoin Copyright in file: ${file}" >&2
          exit 1
      fi
done