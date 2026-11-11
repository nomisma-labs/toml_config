// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: MIT

#include "app_arguments.h"

#include <boost/program_options.hpp>

import std;

import nom.toml_config;

namespace example
{
    app_arguments parse_app_arguments(const std::vector<std::string>& arguments, bool show_help)
    {
        namespace po = boost::program_options;
        app_arguments result;
        result.help = show_help;
        po::options_description description("Application options");
        description.add_options()(
            "name", po::value(&result.name)->default_value("world"), "Greeting recipient; also accepted positionally")(
            "count", po::value(&result.count)->default_value(1), "Number of greetings")(
            "verbose,v", po::bool_switch(&result.verbose), "Print application progress");

        po::positional_options_description positional;
        positional.add("name", 1);
        po::variables_map variables;
        po::store(po::command_line_parser(arguments).options(description).positional(positional).run(), variables);
        po::notify(variables);

        if (result.help)
        {
            std::cout << "Usage: config_args_example [options] [name]\n" << description << '\n';
            nom::tcfg::print_config_help(std::cout);
            return result;
        }
        if (result.count <= 0)
        {
            throw std::invalid_argument("--count must be positive");
        }
        if (result.name.empty())
        {
            throw std::invalid_argument("--name must not be empty");
        }
        return result;
    }
} // namespace example
