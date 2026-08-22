# SPDX-License-Identifier: GPL-2.0-or-later
# This file is part of FigTreeKit; see LICENSE and NOTICE for licensing terms.
"""Enumerations for FigTree-compatible settings."""

# Copyright (C) 2024-2026 Zeng Zichao
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from enum import Enum


class LayoutType(Enum):
    """Tree layout types supported by FigTree."""
    RECTILINEAR = "RECTILINEAR"
    POLAR = "POLAR"
    RADIAL = "RADIAL"


class TransformType(Enum):
    """Tree transform types."""
    CLADOGRAM = "cladogram"
    PHYLOGRAM = "phylogram"


class RootingType(Enum):
    """Tree rooting types.

    Values match the display strings used by FigTree 1.4.4's
    ``TreePreferences.java`` (not the Java constant names).
    """
    USER_SELECTION = "User Selection"
    MID_POINT = "Mid-point"


class OrderType(Enum):
    """Node ordering types.

    Values match the display strings used by FigTree 1.4.4's
    ``TreePreferences.java`` (not the Java constant names).
    """
    INCREASING_NODE_DENSITY = "Increasing Node Density"
    DECREASING_NODE_DENSITY = "Decreasing Node Density"


class FontStyle(Enum):
    """Font style constants mapping to Java ``Font`` style values.

    These correspond to the integer codes used in ``java.awt.Font``:
    PLAIN=0, BOLD=1, ITALIC=2, BOLD|ITALIC=3.
    """
    PLAIN = 0
    BOLD = 1
    ITALIC = 2
    BOLD_ITALIC = 3
