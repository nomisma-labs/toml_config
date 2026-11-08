# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

foreach(test_case IN ITEMS integer_member integer_container unregistered_type)
    execute_process(COMMAND ${CMAKE_COMMAND} --build "${build_dir}" --target reject_${test_case}
        RESULT_VARIABLE status OUTPUT_VARIABLE output ERROR_VARIABLE diagnostic)
    if(status STREQUAL "0")
        message(FATAL_ERROR "${test_case}: disabled config type unexpectedly compiled")
    endif()
    if(NOT "${output}${diagnostic}" MATCHES "NOM_TCONFIG member type is not config-enabled")
        message(FATAL_ERROR "${test_case}: unexpected compilation failure:\n${output}\n${diagnostic}")
    endif()
endforeach()
