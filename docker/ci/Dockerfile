# SPDX-FileCopyrightText: 2026 Alexey Tkachenko
# SPDX-License-Identifier: LicenseRef-Nomisma-Labs-Proprietary
#
# CI image for all Nomisma repos: the toolchain from docs/build.md. Built and published by
# .github/workflows/ci_image.yml.
FROM ubuntu:26.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates git python3 \
      g++-16 cmake ninja-build \
      clang-19 clang-tools-19 clang-tidy-19 clang-format-19 clangd-19 \
      catch2 libboost-log-dev libboost-iostreams-dev libboost-filesystem-dev \
      libboost-thread-dev libboost-date-time-dev libboost-program-options-dev libboost-url-dev \
      libssl-dev libfmt-dev nlohmann-json3-dev zlib1g-dev capnproto libcapnp-dev \
 && rm -rf /var/lib/apt/lists/*
