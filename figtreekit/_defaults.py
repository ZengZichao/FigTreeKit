"""FigTree default settings from Java source code."""

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

from typing import Any, Dict


def get_figtree_defaults() -> Dict[str, Dict[str, Any]]:
    """Return default FigTree settings extracted from ``TreeAppearanceController.java``
    and related controllers in FigTree 1.4.4 source."""
    return {
        "appearance": {
            "foregroundColour": "#000000",
            "backgroundColour": "#ffffff",
            "selectionColour": "#2d3680",
            "branchLineWidth": 1.0,
            "branchColorAttribute": "None",
            "branchColorGradient": False,
            "hilightingGradient": False,
            "backgroundColorAttribute": "None",
            "branchWidthAttribute": "None",
            "branchMinLineWidth": 1.0,
        },
        "layout": {
            "layoutType": "RECTILINEAR",
            "expansion": 50,
            "zoom": 1.0,
        },
        "trees": {
            "rooting": False,
            "rootingType": "User Selection",
            "transform": False,
            "transformType": "cladogram",
            "order": False,
            "orderType": "Increasing Node Density",
        },
        "tipLabels": {
            "isShown": True,
            "fontName": "sansserif",
            "fontSize": 12,
            "fontStyle": 0,
            "displayAttribute": "Names",
            "colorAttribute": "None",
            "significantDigits": 4,
        },
        "nodeLabels": {
            "isShown": False,
            "fontName": "sansserif",
            "fontSize": 12,
            "fontStyle": 0,
            "displayAttribute": "Node ages",
            "colorAttribute": "None",
            "significantDigits": 4,
        },
        "branchLabels": {
            "isShown": False,
            "fontName": "sansserif",
            "fontSize": 12,
            "fontStyle": 0,
            "displayAttribute": "Branch times",
            "colorAttribute": "None",
            "significantDigits": 4,
        },
        "scaleBar": {
            "isShown": True,
            "automaticScale": True,
            "scaleRange": 0.1,
            "fontName": "sansserif",
            "fontSize": 12,
            "fontStyle": 0,
            "lineWidth": 1.0,
            "significantDigits": 4,
            "colour": "#000000",
        },
        "scaleAxis": {
            "isShown": False,
            "automaticScale": True,
            "reverseAxis": False,
            "showGrid": False,
            "fontName": "sansserif",
            "fontSize": 12,
            "fontStyle": 0,
            "lineWidth": 1.0,
            "majorTicks": 0.1,
            "origin": 0.0,
            "significantDigits": 4,
            "tickDirection": "in",
            "colour": "#000000",
        },
        "scale": {
            "rootAge": 1.0,
            "scaleRoot": False,
            "scaleFactor": 1.0,
            "offsetAge": 0.0,
            "autoScale": True,
        },
        "polarLayout": {
            "alignTipLabels": True,
            "angularRange": 0,
            "rootAngle": 0,
            "rootLength": 10,
            "showRoot": False,
        },
        "radialLayout": {
            "spread": 0.5,
            "alignTipLabels": True,
        },
        "rectilinearLayout": {
            "alignTipLabels": True,
            "curvature": 0,
            "rootLength": 10,
        },
        "nodeBars": {
            "isShown": False,
            "barWidth": 1.0,
            "attribute": "height_95%_HPD",
            "colorAttribute": "None",
            "colour": "#000000",
            "fontSize": 12,
            "fontStyle": 0,
            "significantDigits": 4,
        },
        "nodeShapes": {
            "isShown": False,
            "attribute": "None",
            "colorAttribute": "None",
            "shapeType": "circle",
            "colour": "#000000",
            "size": 4.0,
            "fontSize": 12,
            "fontStyle": 0,
            "significantDigits": 4,
            "strokeWidth": 1.0,
        },
        "legend": {
            "isShown": False,
            "position": "Top",
            "x": 0.0,
            "y": 0.0,
            "fontSize": 12,
            "fontStyle": 0,
            "colour": "#000000",
            "backgroundColour": "#ffffff",
            "backgroundOpacity": 0.8,
            "borderWidth": 1.0,
            "reverseOrder": False,
            "isVisible": True,
        },
        "hilighting": {
            "isShown": False,
            "gradient": False,
        },
    }
