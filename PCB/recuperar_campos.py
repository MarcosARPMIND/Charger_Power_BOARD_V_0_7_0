#!/usr/bin/env python3
"""
recuperar_campos.py - repõe MPN / Distributor_PN / Distributor a partir dos
valores que existiam no netlist Charger_Power_BOARD_V_0_7_0.net (exportado a
2026-10-08 11:14), antes de os campos Ref_Mouser, Manufacturer_Part_Number,
MP, Mouser Part Number e Distribuidor terem sido apagados.

Regras de segurança:
  - só preenche campos que estejam VAZIOS (nunca substitui o que já lá está);
  - se o Value ou o Footprint do componente mudaram desde o netlist, não mexe
    e avisa (o componente pode ter sido trocado);
  - se o campo não existir no símbolo, cria-o escondido.

Precisa do migrar_campos.py na mesma pasta. Ordem recomendada:
  1. python3 migrar_campos.py <folhas> --apply      (Ref -> MPN)
  2. python3 recuperar_campos.py <folhas>            (teste)
  3. python3 recuperar_campos.py <folhas> --apply
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from migrar_campos import Node, parse, raw, unquote, quote, head, symbol_props, in_bom

# referência -> valores do netlist (Field4..Field8 e o PN errado do C88 excluídos)
DATA = {
    "C1": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_1206_3216Metric", "value": "10uF"},
    "C2": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C23": {"MPN": "R463I310000M1K", "footprint": "Capacitor_THT:C_Rect_L18.0mm_W5.0mm_P15.00mm_FKS3_FKP3", "value": "100nF"},
    "C24": {"MPN": "16YXM220MEFR8X11.5", "footprint": "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", "value": "220uF"},
    "C25": {"MPN": "CC0603JRX7R9BB473", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "220nF"},
    "C26": {"MPN": "R463I310000M1K", "footprint": "Capacitor_THT:C_Rect_L18.0mm_W5.0mm_P15.00mm_FKS3_FKP3", "value": "100nF"},
    "C27": {"MPN": "885012006061", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "470pF"},
    "C28": {"MPN": "885012006061", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "47nF"},
    "C29": {"MPN": "CL10B105KB8NQNC", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "1uF"},
    "C30": {"MPN": "CL10B104MB8NNNC", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "100nF"},
    "C31": {"MPN": "16YXM220MEFR8X11.5", "footprint": "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", "value": "220uF"},
    "C32": {"MPN": "CC0603JRX7R9BB473", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "220nF"},
    "C33": {"MPN": "885012006061", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "470pF"},
    "C34": {"MPN": "885012006061", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "47nF"},
    "C35": {"MPN": "CL10B105KB8NQNC", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "1uF"},
    "C36": {"MPN": "CL10B104MB8NNNC", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "100nF"},
    "C37": {"MPN": "R463I310000M1K", "footprint": "Capacitor_THT:C_Rect_L18.0mm_W5.0mm_P15.00mm_FKS3_FKP3", "value": "100nF"},
    "C38": {"MPN": "16YXM220MEFR8X11.5", "footprint": "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", "value": "220uF"},
    "C39": {"MPN": "CC0603JRX7R9BB473", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "220nF"},
    "C40": {"MPN": "885012006061", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "470pF"},
    "C41": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "4pF"},
    "C42": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "4pF"},
    "C43": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C44": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C45": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C46": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "33nF"},
    "C47": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C48": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C49": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "220pF"},
    "C50": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "1uF"},
    "C51": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "1uF"},
    "C52": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "10nF"},
    "C53": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "1uF"},
    "C54": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "1uF"},
    "C55": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "1uF"},
    "C56": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "1.5nF"},
    "C57": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "1uF"},
    "C58": {"MPN": "885012006061", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "47nF"},
    "C59": {"MPN": "CL10B105KB8NQNC", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "1uF"},
    "C60": {"MPN": "CL10B104MB8NNNC", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "100nF"},
    "C61": {"MPN": "R463I310000M1K", "footprint": "Capacitor_THT:C_Rect_L18.0mm_W5.0mm_P15.00mm_FKS3_FKP3", "value": "100nF"},
    "C62": {"MPN": "16YXM220MEFR8X11.5", "footprint": "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", "value": "220uF"},
    "C63": {"MPN": "CC0603JRX7R9BB473", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "220nF"},
    "C64": {"MPN": "885012006061", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "470pF"},
    "C65": {"MPN": "885012006061", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "47nF"},
    "C66": {"MPN": "CL10B105KB8NQNC", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "1uF"},
    "C67": {"MPN": "CL10B104MB8NNNC", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "100nF"},
    "C70": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_1206_3216Metric", "value": "10uF"},
    "C71": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C72": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C73": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "33nF"},
    "C74": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "33nF"},
    "C75": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "30pF"},
    "C76": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "30pF"},
    "C77": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C78": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C79": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C80": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C81": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C82": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C83": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C84": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C103": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "33nF"},
    "C104": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C105": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C106": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "33nF"},
    "C107": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "33nF"},
    "C108": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C109": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C110": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_1206_3216Metric", "value": "10uF"},
    "C111": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C112": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C113": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "30pF"},
    "C114": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "30pF"},
    "C115": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C116": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C117": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C118": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C119": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "33nF"},
    "C120": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "33nF"},
    "C121": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C122": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C123": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_1206_3216Metric", "value": "10uF"},
    "C124": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C125": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "C126": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "30pF"},
    "C127": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric_Pad1.08x0.95mm_HandSolder", "value": "30pF"},
    "C128": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0805_2012Metric", "value": "4.7uF"},
    "C129": {"Distributor": "Mouser", "footprint": "Capacitor_SMD:C_0603_1608Metric", "value": "0.1uF"},
    "D1": {"Distributor": "Mouser", "footprint": "Package_TO_SOT_SMD:SOT-23-3", "value": "CDSOT23-SM712"},
    "D7": {"MPN": "BZT52-B5V6J", "footprint": "Diode_SMD:D_SOD-123", "value": "5V6"},
    "D10": {"Distributor": "Mouser", "footprint": "Diode_SMD:D_SMA", "value": "SMAJ14CA"},
    "D11": {"Distributor": "Mouser", "footprint": "Package_TO_SOT_SMD:SOT-23", "value": "BAT54S"},
    "D12": {"Distributor": "Mouser", "footprint": "Package_TO_SOT_SMD:SOT-23", "value": "BAT54S"},
    "D13": {"Distributor": "Mouser", "footprint": "Package_TO_SOT_SMD:SOT-23", "value": "BAT54S"},
    "D14": {"Distributor": "Mouser", "footprint": "Package_TO_SOT_SMD:SOT-23", "value": "BAT54S"},
    "D16": {"MPN": "RS1MFP", "footprint": "Diode_SMD:D_SOD-123", "value": "RS1MFP"},
    "D18": {"Distributor": "Mouser", "footprint": "Diode_SMD:D_SMA", "value": "SS12"},
    "D22": {"Distributor": "Mouser", "footprint": "Diode_SMD:D_SMA", "value": "SS12"},
    "D25": {"MPN": "RS1MFP", "footprint": "Diode_SMD:D_SOD-123", "value": "RS1MFP"},
    "D28": {"MPN": "SMAJ400A", "footprint": "FOOTPRINTS:DIOM5026X229N", "value": "SMAJ400A"},
    "D29": {"MPN": "BZT52-B5V6J", "footprint": "Diode_SMD:D_SOD-123", "value": "5V6"},
    "D30": {"MPN": "RS1MFP", "footprint": "Diode_SMD:D_SOD-123", "value": "RS1MFP"},
    "D31": {"MPN": "RS1MFP", "footprint": "Diode_SMD:D_SOD-123", "value": "RS1MFP"},
    "D48": {"MPN": "SMAJ400A", "footprint": "FOOTPRINTS:DIOM5026X229N", "value": "SMAJ400A"},
    "D49": {"MPN": "BZT52-B5V6J", "footprint": "Diode_SMD:D_SOD-123", "value": "5V6"},
    "D50": {"MPN": "RS1MFP", "footprint": "Diode_SMD:D_SOD-123", "value": "RS1MFP"},
    "D51": {"MPN": "RS1MFP", "footprint": "Diode_SMD:D_SOD-123", "value": "RS1MFP"},
    "D52": {"MPN": "SMAJ400A", "footprint": "FOOTPRINTS:DIOM5026X229N", "value": "SMAJ400A"},
    "D53": {"MPN": "BZT52-B5V6J", "footprint": "Diode_SMD:D_SOD-123", "value": "5V6"},
    "D54": {"MPN": "RS1MFP", "footprint": "Diode_SMD:D_SOD-123", "value": "RS1MFP"},
    "D55": {"MPN": "RS1MFP", "footprint": "Diode_SMD:D_SOD-123", "value": "RS1MFP"},
    "D56": {"MPN": "SMAJ400A", "footprint": "FOOTPRINTS:DIOM5026X229N", "value": "SMAJ400A"},
    "IC9": {"Distributor": "Mouser", "footprint": "FOOTPRINTS:QFP50P900X900X160-48N", "value": "STM32C031C6T6"},
    "IC10": {"Distributor": "Mouser", "Distributor_PN": "595-TLA431AIDBZR", "MPN": "TLA431AIDBZR", "footprint": "FOOTPRINTS:SOT95P237X112-3N", "value": "TLA431AIDBZR"},
    "IC15": {"MPN": "VO618A-3X017T", "footprint": "FOOTPRINTS:SMD-4_OPTION_7", "value": "VO618A-3X017T"},
    "IC16": {"MPN": "LM4040C30FTA", "footprint": "Package_TO_SOT_SMD:SOT-23-3", "value": "LM4040C30FTA"},
    "IC17": {"MPN": "MCP6541RT-I/OT", "footprint": "FOOTPRINTS:SOT95P280X145-5N", "value": "MCP6541RT-I_OT"},
    "IC18": {"MPN": "VO618A-3X017T", "footprint": "FOOTPRINTS:SMD-4_OPTION_7", "value": "VO618A-3X017T"},
    "IC19": {"Distributor": "Mouser", "Distributor_PN": "595-TPS54302DDCT", "MPN": "TPS54302DDCT", "footprint": "FOOTPRINTS:SOT95P280X110-6N", "value": "TPS54302DDCT"},
    "IC20": {"MPN": "74LVC1G17GW,125", "footprint": "FOOTPRINTS:SOT65P212X110-5N", "value": "74LVC1G17GW,125"},
    "IC21": {"MPN": "VO618A-3X017T", "footprint": "FOOTPRINTS:SMD-4_OPTION_7", "value": "VO618A-3X017T"},
    "IC22": {"MPN": "LM4040C30FTA", "footprint": "Package_TO_SOT_SMD:SOT-23-3", "value": "LM4040C30FTA"},
    "IC23": {"MPN": "MCP6541RT-I/OT", "footprint": "FOOTPRINTS:SOT95P280X145-5N", "value": "MCP6541RT-I_OT"},
    "IC24": {"MPN": "VO618A-3X017T", "footprint": "FOOTPRINTS:SMD-4_OPTION_7", "value": "VO618A-3X017T"},
    "IC25": {"MPN": "74LVC1G17GW,125", "footprint": "FOOTPRINTS:SOT65P212X110-5N", "value": "74LVC1G17GW,125"},
    "IC26": {"MPN": "VO618A-3X017T", "footprint": "FOOTPRINTS:SMD-4_OPTION_7", "value": "VO618A-3X017T"},
    "IC27": {"MPN": "LM4040C30FTA", "footprint": "Package_TO_SOT_SMD:SOT-23-3", "value": "LM4040C30FTA"},
    "IC28": {"Distributor": "Mouser", "Distributor_PN": "771-LM75BD118", "MPN": "LM75BD,118", "footprint": "FOOTPRINTS:SOIC127P600X175-8N", "value": "LM75BD,118"},
    "IC45": {"MPN": "MCP6541RT-I/OT", "footprint": "FOOTPRINTS:SOT95P280X145-5N", "value": "MCP6541RT-I_OT"},
    "IC46": {"MPN": "VO618A-3X017T", "footprint": "FOOTPRINTS:SMD-4_OPTION_7", "value": "VO618A-3X017T"},
    "IC47": {"MPN": "74LVC1G17GW,125", "footprint": "FOOTPRINTS:SOT65P212X110-5N", "value": "74LVC1G17GW,125"},
    "IC48": {"MPN": "VO618A-3X017T", "footprint": "FOOTPRINTS:SMD-4_OPTION_7", "value": "VO618A-3X017T"},
    "IC49": {"MPN": "LM4040C30FTA", "footprint": "Package_TO_SOT_SMD:SOT-23-3", "value": "LM4040C30FTA"},
    "IC50": {"MPN": "MCP6541RT-I/OT", "footprint": "FOOTPRINTS:SOT95P280X145-5N", "value": "MCP6541RT-I_OT"},
    "IC51": {"MPN": "VO618A-3X017T", "footprint": "FOOTPRINTS:SMD-4_OPTION_7", "value": "VO618A-3X017T"},
    "IC52": {"MPN": "74LVC1G17GW,125", "footprint": "FOOTPRINTS:SOT65P212X110-5N", "value": "74LVC1G17GW,125"},
    "J1": {"MPN": "AMT0440005TH0000G", "footprint": "FOOTPRINTS:AMT0440005TH0000G", "value": "AMT0440005TH0000G"},
    "J3": {"MPN": "AMT0440005TH0000G", "footprint": "FOOTPRINTS:AMT0440005TH0000G", "value": "AMT0440005TH0000G"},
    "J5": {"MPN": "AMT0440005TH0000G", "footprint": "FOOTPRINTS:AMT0440005TH0000G", "value": "AMT0440005TH0000G"},
    "J6": {"Distributor": "Mouser", "Distributor_PN": "306-B6BXHALFSN", "MPN": "B6B-XH-A(LF)(SN)", "footprint": "FOOTPRINTS:SHDR6W64P0X250_1X6_1740X575X700P", "value": "B6B-XH-A_LF__SN_"},
    "J7": {"MPN": "AMT0440005TH0000G", "footprint": "FOOTPRINTS:AMT0440005TH0000G", "value": "AMT0440005TH0000G"},
    "J9": {"Distributor": "Mouser", "Distributor_PN": "306-B6BXHALFSN", "MPN": "B6B-XH-A(LF)(SN)", "footprint": "FOOTPRINTS:SHDR6W64P0X250_1X6_1740X575X700P", "value": "B6B-XH-A_LF__SN_"},
    "J10": {"MPN": "AMT0440005TH0000G", "footprint": "FOOTPRINTS:AMT0440005TH0000G", "value": "AMT0440005TH0000G"},
    "J11": {"MPN": "AMT0440005TH0000G", "footprint": "FOOTPRINTS:AMT0440005TH0000G", "value": "AMT0440005TH0000G"},
    "J12": {"MPN": "AMT0440005TH0000G", "footprint": "FOOTPRINTS:AMT0440005TH0000G", "value": "AMT0440005TH0000G"},
    "J13": {"MPN": "AMT0440005TH0000G", "footprint": "FOOTPRINTS:AMT0440005TH0000G", "value": "AMT0440005TH0000G"},
    "J14": {"MPN": "AMT0440005TH0000G", "footprint": "FOOTPRINTS:AMT0440005TH0000G", "value": "AMT0440005TH0000G"},
    "J15": {"MPN": "AMT0440005TH0000G", "footprint": "FOOTPRINTS:AMT0440005TH0000G", "value": "AMT0440005TH0000G"},
    "L1": {"Distributor": "Mouser", "Distributor_PN": "652-SRP7028CC-6R8M", "MPN": "SRP7028CC-6R8M", "footprint": "FOOTPRINTS:INDPM7366X300N", "value": "SRP7028CC-6R8M"},
    "Q5": {"Distributor": "Mouser", "footprint": "Package_TO_SOT_SMD:SOT-23", "value": "BSS316N H6327"},
    "Q6": {"Distributor": "Mouser", "footprint": "Package_TO_SOT_SMD:SOT-23", "value": "BSS316N H6327"},
    "Q7": {"MPN": "DMN60H080DS-13", "footprint": "Package_TO_SOT_SMD:SOT-23-3", "value": "DMN60H080DS"},
    "Q8": {"MPN": "DMN60H080DS-13", "footprint": "Package_TO_SOT_SMD:SOT-23-3", "value": "DMN60H080DS"},
    "Q9": {"MPN": "DMN60H080DS-13", "footprint": "Package_TO_SOT_SMD:SOT-23-3", "value": "DMN60H080DS"},
    "Q10": {"MPN": "DMN60H080DS-13", "footprint": "Package_TO_SOT_SMD:SOT-23-3", "value": "DMN60H080DS"},
    "R1": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R2": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10R"},
    "R3": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10R"},
    "R27": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R45": {"MPN": "CMP1206-FX-1001ELF", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "1k"},
    "R46": {"MPN": "CMP1206-FX-1001ELF", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "1k"},
    "R47": {"MPN": "RCV1206470KFKEA", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "470k"},
    "R48": {"MPN": "AC0603FR-072K2L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "2K2"},
    "R49": {"MPN": "RMCF0603FT1K50", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "1K5"},
    "R50": {"MPN": "RCS060310K0FKEA", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R52": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "20K"},
    "R53": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "1K"},
    "R54": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "20K"},
    "R56": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "54K9"},
    "R57": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "75K"},
    "R59": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R60": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R61": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R62": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R63": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R64": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0805_2012Metric", "value": "47R"},
    "R65": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "38K3"},
    "R66": {"MPN": "CRG0603F39R", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "39R"},
    "R68": {"MPN": "FMP200JR-52-22K", "footprint": "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P12.70mm_Horizontal", "value": "22K"},
    "R69": {"MPN": "FMP200JR-52-22K", "footprint": "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P12.70mm_Horizontal", "value": "22K"},
    "R70": {"MPN": "CRG0603F68K", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "68K"},
    "R71": {"MPN": "RC0603FR-078K87L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "8K87"},
    "R72": {"MPN": "RC0603FR-10470KL", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "470k"},
    "R73": {"MPN": "RE0603FRE071K8L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "1K8"},
    "R74": {"MPN": "CRCW0603100KFKEC", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100K"},
    "R75": {"MPN": "CRGCQ0603F4K7", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "4K7"},
    "R76": {"MPN": "CMP1206-FX-1001ELF", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "1k"},
    "R77": {"MPN": "CMP1206-FX-1001ELF", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "1k"},
    "R78": {"MPN": "RCV1206470KFKEA", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "470k"},
    "R79": {"MPN": "AC0603FR-072K2L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "2K2"},
    "R80": {"MPN": "RMCF0603FT1K50", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "1K5"},
    "R81": {"MPN": "RCS060310K0FKEA", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R82": {"MPN": "CRG0603F39R", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "39R"},
    "R83": {"MPN": "FMP200JR-52-22K", "footprint": "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P12.70mm_Horizontal", "value": "22K"},
    "R84": {"MPN": "FMP200JR-52-22K", "footprint": "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P12.70mm_Horizontal", "value": "22K"},
    "R85": {"MPN": "CRG0603F68K", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "68K"},
    "R86": {"MPN": "RC0603FR-078K87L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "8K87"},
    "R87": {"MPN": "RC0603FR-10470KL", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "470k"},
    "R88": {"MPN": "RE0603FRE071K8L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "1K8"},
    "R89": {"MPN": "CRCW0603100KFKEC", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100K"},
    "R90": {"MPN": "CRGCQ0603F4K7", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "4K7"},
    "R91": {"MPN": "CMP1206-FX-1001ELF", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "1k"},
    "R92": {"MPN": "CMP1206-FX-1001ELF", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "1k"},
    "R93": {"MPN": "RCV1206470KFKEA", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "470k"},
    "R94": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R95": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100R"},
    "R96": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "15R8"},
    "R97": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R98": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "24K"},
    "R102": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100R"},
    "R103": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "24K"},
    "R105": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R106": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "120R"},
    "R109": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "120R"},
    "R110": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100R"},
    "R112": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100R"},
    "R114": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R115": {"MPN": "AC0603FR-072K2L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "2K2"},
    "R116": {"MPN": "RMCF0603FT1K50", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "1K5"},
    "R117": {"MPN": "RCS060310K0FKEA", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R118": {"MPN": "CRG0603F39R", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "39R"},
    "R119": {"MPN": "FMP200JR-52-22K", "footprint": "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P12.70mm_Horizontal", "value": "22K"},
    "R120": {"MPN": "FMP200JR-52-22K", "footprint": "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P12.70mm_Horizontal", "value": "22K"},
    "R121": {"MPN": "CRG0603F68K", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "68K"},
    "R122": {"MPN": "RC0603FR-078K87L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "8K87"},
    "R123": {"MPN": "RC0603FR-10470KL", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "470k"},
    "R124": {"MPN": "RE0603FRE071K8L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "1K8"},
    "R125": {"MPN": "CRCW0603100KFKEC", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100K"},
    "R126": {"MPN": "CRGCQ0603F4K7", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "4K7"},
    "R127": {"MPN": "CMP1206-FX-1001ELF", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "1k"},
    "R128": {"MPN": "CMP1206-FX-1001ELF", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "1k"},
    "R129": {"MPN": "RCV1206470KFKEA", "footprint": "Resistor_SMD:R_1206_3216Metric", "value": "470k"},
    "R130": {"MPN": "AC0603FR-072K2L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "2K2"},
    "R131": {"MPN": "RMCF0603FT1K50", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "1K5"},
    "R132": {"MPN": "RCS060310K0FKEA", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R133": {"MPN": "CRG0603F39R", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "39R"},
    "R134": {"MPN": "FMP200JR-52-22K", "footprint": "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P12.70mm_Horizontal", "value": "22K"},
    "R135": {"MPN": "FMP200JR-52-22K", "footprint": "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P12.70mm_Horizontal", "value": "22K"},
    "R136": {"MPN": "CRG0603F68K", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "68K"},
    "R137": {"MPN": "RC0603FR-078K87L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "8K87"},
    "R138": {"MPN": "RC0603FR-10470KL", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "470k"},
    "R139": {"MPN": "RE0603FRE071K8L", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "1K8"},
    "R140": {"MPN": "CRCW0603100KFKEC", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100K"},
    "R141": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "22K"},
    "R142": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "5K1"},
    "R144": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R145": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "2K2"},
    "R146": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "2K2"},
    "R147": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "120R"},
    "R148": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "2K2"},
    "R149": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "15R8"},
    "R150": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100R"},
    "R151": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100R"},
    "R152": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R153": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R154": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "24K"},
    "R158": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "15R8"},
    "R159": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100R"},
    "R160": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "100R"},
    "R161": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R162": {"Distributor": "Mouser", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "10K"},
    "R215": {"MPN": "CRGCQ0603F4K7", "footprint": "Resistor_SMD:R_0603_1608Metric", "value": "4K7"},
    "SW1": {"Distributor": "Mouser", "footprint": "Button_Switch_SMD:SW_SPST_B3U-1000P", "value": "SW_SPST"},
    "SW2": {"Distributor": "Mouser", "footprint": "Button_Switch_SMD:SW_SPST_B3U-1000P", "value": "SW_SPST"},
    "T7": {"MPN": "ZMPT101B", "footprint": "FOOTPRINTS:XFMR_ZMPT101B", "value": "ZMPT101B"},
    "T9": {"MPN": "ZMPT101B", "footprint": "FOOTPRINTS:XFMR_ZMPT101B", "value": "ZMPT101B"},
    "T11": {"MPN": "ZMPT101B", "footprint": "FOOTPRINTS:XFMR_ZMPT101B", "value": "ZMPT101B"},
    "U4": {"Distributor": "Mouser", "footprint": "FOOTPRINTS:SOT95P280X145-6N", "value": "TLV1805DBVR"},
    "U5": {"Distributor": "Mouser", "footprint": "FOOTPRINTS:SOT95P280X145-6N", "value": "TLV1805DBVR"},
    "U6": {"Distributor": "Mouser", "footprint": "FOOTPRINTS:LFCSP-28-1EP_5x5mm_P0.5mm_EP3.14x3.14mm_ThermalVias_MigCOM", "value": "ADE7953xCP"},
    "U7": {"Distributor": "Mouser", "footprint": "FOOTPRINTS:LFCSP-28-1EP_5x5mm_P0.5mm_EP3.14x3.14mm_ThermalVias_MigCOM", "value": "ADE7953xCP"},
    "U9": {"Distributor": "Mouser", "footprint": "FOOTPRINTS:LFCSP-28-1EP_5x5mm_P0.5mm_EP3.14x3.14mm_ThermalVias_MigCOM", "value": "ADE7953xCP"},
    "Y3": {"Distributor": "Mouser", "footprint": "Crystal:Crystal_SMD_2016-4Pin_2.0x1.6mm", "value": "CX2016FB48000C0FZZH1"},
    "Y4": {"Distributor": "Mouser", "footprint": "Crystal:Crystal_SMD_HC49-SD", "value": "GC0350016"},
    "Y5": {"Distributor": "Mouser", "footprint": "Crystal:Crystal_SMD_HC49-SD", "value": "GC0350016"},
    "Y6": {"Distributor": "Mouser", "footprint": "Crystal:Crystal_SMD_HC49-SD", "value": "GC0350016"}
}

FIELDS = ("MPN", "Distributor", "Distributor_PN")


def symbol_refs(s, sym, props):
    """Todas as referências do símbolo (folhas partilhadas têm várias)."""
    refs = []
    if "Reference" in props:
        refs.append(props["Reference"]["val"])

    def walk(n):
        for it in n.items:
            if isinstance(it, Node):
                if head(s, it) == "reference" and len(it.items) > 1:
                    refs.append(unquote(raw(s, it.items[1])))
                walk(it)
    walk(sym)
    return list(dict.fromkeys(refs))


def new_property(name, value, indent, at):
    i = indent
    return (f'(property "{name}" {quote(value)}\n'
            f'{i}\t(at {at} 0)\n'
            f'{i}\t(effects\n{i}\t\t(font\n{i}\t\t\t(size 1.27 1.27)\n{i}\t\t)\n'
            f'{i}\t\t(hide yes)\n{i}\t)\n{i})')


def process(text):
    root = parse(text)
    edits, log, skipped = [], [], []
    for sym in (n for n in root.items if isinstance(n, Node) and head(text, n) == "symbol"):
        props = symbol_props(text, sym)
        refs = symbol_refs(text, sym, props)
        ref = next((r for r in refs if r in DATA), None)
        if ref is None:
            continue
        e = DATA[ref]
        cur_val = props.get("Value", {}).get("val", "")
        cur_fp = props.get("Footprint", {}).get("val", "")
        if cur_val != e["value"] or cur_fp != e["footprint"]:
            todo = [f for f in FIELDS if e.get(f) and not props.get(f, {}).get("val", "").strip()]
            if todo:
                skipped.append(f"  {ref:8} mudou desde o netlist: "
                               f"'{e['value']}' {e['footprint'].split(':')[-1]} -> "
                               f"'{cur_val}' {cur_fp.split(':')[-1]}  (tinha {e.get('MPN') or e.get('Distributor_PN')})")
            continue

        inserts = []
        for f in FIELDS:
            v = e.get(f)
            if not v:
                continue
            if f in props:
                if props[f]["val"].strip():
                    continue
                t = props[f]["val_tok"]
                edits.append((t[1], t[2], quote(v)))
            else:
                inserts.append((f, v))
            log.append(f"  {ref:8} {f} = {v}")

        if inserts:
            last = [it for it in sym.items if isinstance(it, Node) and head(text, it) == "property"][-1]
            ls = text.rfind("\n", 0, last.start) + 1
            indent = text[ls:last.start]
            at = "0 0"
            for it in sym.items:
                if isinstance(it, Node) and head(text, it) == "at" and len(it.items) >= 3:
                    at = f"{raw(text, it.items[1])} {raw(text, it.items[2])}"
            block = "".join("\n" + indent + new_property(f, v, indent, at) for f, v in inserts)
            edits.append((last.end, last.end, block))

    edits.sort(key=lambda x: x[0], reverse=True)
    out = text
    for a, b, new in edits:
        out = out[:a] + new + out[b:]
    parse(out)
    return out, log, skipped, len(edits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    total = 0
    for f in map(Path, args.files):
        with open(f, encoding="utf-8", newline="") as fh:
            text = fh.read()
        try:
            new, log, skipped, n = process(text)
        except Exception as ex:
            print(f"\n[ERRO] {f.name}: {ex} - não alterado")
            continue
        print(f"\n=== {f.name}: {len(log)} campos repostos ===")
        print("\n".join(log) if log else "  (nada a repor)")
        if skipped:
            print("  NÃO REPOSTOS (verifica à mão):")
            print("\n".join(skipped))
        total += len(log)
        if args.apply and n:
            shutil.copy2(f, f.with_name(f"{f.name}.{stamp}.bak"))
            with open(f, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
    print(f"\nTotal: {total} campos.", "Gravado." if args.apply else "Modo de teste: nada gravado.")


if __name__ == "__main__":
    main()
