# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

include_guard(GLOBAL)

# Generated files usually do not exist during configuration. REAL_PATH requires an
# existing path, so resolve its nearest existing ancestor and preserve the missing suffix.
function(_tcfg_canonical_path path result)
    set(ancestor "${path}")
    set(suffix "")
    set(symlink_count 0)
    while(NOT EXISTS "${ancestor}")
        cmake_path(GET ancestor PARENT_PATH parent)
        if(IS_SYMLINK "${ancestor}")
            math(EXPR symlink_count "${symlink_count} + 1")
            if(symlink_count GREATER 64)
                message(FATAL_ERROR "tcfg_generate: cannot resolve symlink chain in '${path}'")
            endif()
            file(READ_SYMLINK "${ancestor}" link)
            cmake_path(ABSOLUTE_PATH link BASE_DIRECTORY "${parent}"
                NORMALIZE OUTPUT_VARIABLE ancestor)
        else()
            cmake_path(GET ancestor FILENAME leaf)
            set(suffix "/${leaf}${suffix}")
            set(ancestor "${parent}")
        endif()
    endwhile()
    file(REAL_PATH "${ancestor}" canonical)
    string(APPEND canonical "${suffix}")
    cmake_path(NORMAL_PATH canonical)
    set(${result} "${canonical}" PARENT_SCOPE)
endfunction()

# tcfg_generate(TARGET <existing-target> INPUT <tcfg> OUTPUT <toml>
#               [OVERLAYS <files>...] [SET <key=TOML>...]
#               [DEPENDS <files>...] [INSTALL_DESTINATION <directory>])
#
# Relative inputs are relative to the calling source directory; relative outputs are
# relative to its binary directory. A depfile tracks every transitive include. Output
# content is replaced atomically by the CLI, and unchanged output keeps its timestamp.
# Each canonical output has one producer. Installation follows the owning target's
# EXCLUDE_FROM_ALL property and the kit's nom_install setting when that setting exists.
# Environment variables are not file dependencies: after changing a referenced variable,
# delete the generated output or list a caller-managed environment stamp in DEPENDS.
function(tcfg_generate)
    cmake_parse_arguments(PARSE_ARGV 0 arg "" "TARGET;INPUT;OUTPUT;INSTALL_DESTINATION"
        "OVERLAYS;SET;DEPENDS")
    if(arg_UNPARSED_ARGUMENTS OR arg_KEYWORDS_MISSING_VALUES)
        message(FATAL_ERROR "tcfg_generate: unknown arguments or missing argument values")
    endif()
    foreach(required IN ITEMS TARGET INPUT OUTPUT)
        if(NOT arg_${required})
            message(FATAL_ERROR "tcfg_generate requires ${required}")
        endif()
    endforeach()
    if(NOT TARGET ${arg_TARGET})
        message(FATAL_ERROR "tcfg_generate: TARGET ${arg_TARGET} must already exist")
    endif()

    # Neither configuring nor using the C++ runtime requires Python unless this helper runs.
    find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
    set(python_root "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../../python")
    cmake_path(NORMAL_PATH python_root)
    set(generator "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../../cfggen.py")
    cmake_path(NORMAL_PATH generator)
    if(NOT EXISTS "${generator}" OR NOT EXISTS "${python_root}/toml_config/__main__.py")
        message(FATAL_ERROR "tcfg_generate: missing cfggen.py or Python package under ${python_root}")
    endif()

    cmake_path(ABSOLUTE_PATH arg_INPUT BASE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        NORMALIZE OUTPUT_VARIABLE input)
    cmake_path(ABSOLUTE_PATH arg_OUTPUT BASE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
        NORMALIZE OUTPUT_VARIABLE output)
    _tcfg_canonical_path("${input}" canonical_input)
    _tcfg_canonical_path("${output}" canonical_output)
    if(canonical_input STREQUAL canonical_output)
        message(FATAL_ERROR "tcfg_generate: INPUT and OUTPUT must be different files")
    endif()
    set(depfile "${output}.d")
    foreach(artifact IN ITEMS "${output}" "${depfile}")
        _tcfg_canonical_path("${artifact}" canonical_artifact)
        string(SHA256 artifact_hash "${canonical_artifact}")
        get_property(has_owner GLOBAL PROPERTY "TCFG_OUTPUT_OWNER_${artifact_hash}" SET)
        get_property(previous_owner GLOBAL PROPERTY "TCFG_OUTPUT_OWNER_${artifact_hash}")
        if(has_owner)
            message(FATAL_ERROR
                "tcfg_generate: output '${canonical_artifact}' already belongs to TARGET "
                "'${previous_owner}'; TARGET '${arg_TARGET}' cannot register a second producer")
        endif()
        set_property(GLOBAL PROPERTY "TCFG_OUTPUT_OWNER_${artifact_hash}" "${arg_TARGET}")
    endforeach()
    cmake_path(GET output PARENT_PATH output_directory)
    set(extra_arguments)
    set(overlay_files)
    foreach(overlay IN LISTS arg_OVERLAYS)
        cmake_path(ABSOLUTE_PATH overlay BASE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
            NORMALIZE OUTPUT_VARIABLE overlay_path)
        list(APPEND overlay_files "${overlay_path}")
        list(APPEND extra_arguments --overlay "${overlay_path}")
    endforeach()
    foreach(assignment IN LISTS arg_SET)
        string(REPLACE ";" "\\;" escaped_assignment "${assignment}")
        list(APPEND extra_arguments --set "${escaped_assignment}")
    endforeach()
    file(GLOB_RECURSE generator_sources CONFIGURE_DEPENDS "${python_root}/toml_config/*.py")
    list(APPEND generator_sources "${generator}")

    add_custom_command(OUTPUT "${output}"
        COMMAND ${CMAKE_COMMAND} -E make_directory "${output_directory}"
        COMMAND ${CMAKE_COMMAND} -E env PYTHONDONTWRITEBYTECODE=1
            ${Python3_EXECUTABLE} "${generator}" "${input}" -o "${output}"
            --depfile "${depfile}" ${extra_arguments}
        DEPENDS "${input}" ${overlay_files} ${generator_sources} ${arg_DEPENDS}
        DEPFILE "${depfile}"
        BYPRODUCTS "${depfile}"
        COMMENT "Generating TOML configuration ${output}"
        VERBATIM)
    string(SHA256 output_hash "${output}")
    string(SUBSTRING "${output_hash}" 0 12 output_hash)
    set(config_target "${arg_TARGET}_tcfg_${output_hash}")
    add_custom_target(${config_target} DEPENDS "${output}")
    add_dependencies(${arg_TARGET} ${config_target})

    get_target_property(excluded_from_all ${arg_TARGET} EXCLUDE_FROM_ALL)
    if(arg_INSTALL_DESTINATION AND NOT excluded_from_all
            AND (NOT DEFINED nom_install OR nom_install))
        install(FILES "${output}" DESTINATION "${arg_INSTALL_DESTINATION}")
    endif()
endfunction()

# Install the generator with its helper, preserving their relative layout. Consumers can
# include <prefix>/share/toml_config/cmake/toml_config/tcfg.cmake without installing a Python package.
function(toml_config_install_tooling)
    if(DEFINED nom_install AND NOT nom_install)
        return()
    endif()
    include(GNUInstallDirs)
    install(FILES "${CMAKE_CURRENT_FUNCTION_LIST_FILE}"
        DESTINATION "${CMAKE_INSTALL_DATADIR}/toml_config/cmake/toml_config")
    install(FILES "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../../cfggen.py"
        DESTINATION "${CMAKE_INSTALL_DATADIR}/toml_config")
    install(DIRECTORY "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../../python/toml_config"
        DESTINATION "${CMAKE_INSTALL_DATADIR}/toml_config/python"
        FILES_MATCHING PATTERN "*.py" PATTERN "__pycache__" EXCLUDE)
endfunction()
