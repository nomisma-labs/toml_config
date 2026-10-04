// SPDX-FileCopyrightText: 2026 Alexey Tkachenko
// SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary

module;

#include <metal/list/at.hpp>
#include <metal/list/list.hpp>
#include <metal/number/number.hpp>

export module nom.example:types;

export namespace nom::example
{
    // The dependency stays in the global module fragment; importers instantiate this alias.
    template <unsigned Index, typename... Types>
    using type_at_t = metal::at<metal::list<Types...>, metal::number<Index>>;
} // namespace nom::example
