"""The cables between the rev A boards: pin number -> net name, from
docs/notes/rev_a_board_split.md section 3. Every board script takes its connector's pins from
here, and check_links.py compares the drawn netlists of both ends against it.

None means the pin is not connected at either end.
"""

J_LINK = {  # D to A, 2 x 20.
    1: "GND", 2: "MCLK_MCU", 3: "GND", 4: "BCK", 5: "GND", 6: "LRCK", 7: "GND", 8: "DIN1",
    9: "GND", 10: "DOUT1", 11: "GND", 12: "I2C1_SCL", 13: "I2C1_SDA", 14: "CODEC_RST_N",
    15: "CODEC_OVF", 16: "GND", 17: "OSC_SEL", 18: "OSC_22M_EN", 19: "MUTE_MON",
    20: "MUTE_LINE34", 21: "HP_EN", 22: "RAILS_OK", 23: "GND", 24: "GND", 25: "5V_DIG",
    26: "5V_DIG", 27: "GND", 28: "5V5_PRE", 29: "5V5_PRE", 30: "GND", 31: "GND",
    32: "+15V_RAW", 33: "+15V_RAW", 34: "GND", 35: "GND", 36: "-15V_RAW", 37: "-15V_RAW",
    38: "GND", 39: "GND", 40: "GND",
}

J_PANEL = {  # D to PL, 2 x 20.
    1: "GND", 2: "POT_REF", 3: "POT1", 4: "POT2", 5: "POT3", 6: "POT4", 7: "POT5", 8: "POT6",
    9: "POT7", 10: "POT_GND", 11: "GND", 12: "BTN1", 13: "BTN2", 14: "BTN3", 15: "BTN4",
    16: "BTN5", 17: "GND", 18: "LED1", 19: "LED2", 20: "LED3", 21: "LED4", 22: "LED5",
    23: "LED6", 24: "LED7", 25: "PANEL_3V3", 26: "GND", 27: "ENC1_A", 28: "ENC1_B",
    29: "ENC1_SW", 30: "ENC2_A", 31: "ENC2_B", 32: "ENC2_SW", 33: "GND", 34: "I2C4_SCL",
    35: "I2C4_SDA", 36: "GND", 37: "PANEL_3V3", 38: "GND", 39: None, 40: "GND",
}

J_PJ = {  # PL to PR, 2 x 8.
    1: "POT_REF", 2: "POT1", 3: "POT2", 4: "POT3", 5: "POT4", 6: "POT5", 7: "POT_GND", 8: "GND",
    9: "BTN4", 10: "BTN5", 11: "LED5", 12: "LED6", 13: "PANEL_3V3", 14: "GND", 15: "GND",
    16: "GND",
}

J_HP = {  # A to PR, 2 x 3.
    1: "HP_L", 2: "HP_L_RET", 3: "HP_R_RET", 4: "HP_R", 5: None, 6: None,
}

# Meaning of the panel nets (rev_a_architecture.md 11): POT1 bass, POT2 mid, POT3 treble,
# POT4 monitor volume, POT5 phones volume, POT6 FX amount, POT7 blend; BTN1 FX select, BTN2 FX
# on, BTN3 tap, BTN4 mute, BTN5 dim; LED1 input 1 signal, LED2 input 1 clip, LED3 input 2
# signal, LED4 input 2 clip, LED5 mute, LED6 dim, LED7 FX on.

LINKS = {"J_LINK": J_LINK, "J_PANEL": J_PANEL, "J_PJ": J_PJ, "J_HP": J_HP}

# Which board holds each end. The connector's Value field in the schematic is the link's name.
ENDS = {"J_LINK": ("rev_a_d", "rev_a_a"), "J_PANEL": ("rev_a_d", "rev_a_pl"),
        "J_PJ": ("rev_a_pl", "rev_a_pr"), "J_HP": ("rev_a_a", "rev_a_pr")}


def pins(link):
    """{pin number as str: net} for kisch, and the list of unconnected pins."""
    table = LINKS[link]
    return ({str(k): v for k, v in table.items() if v is not None},
            [str(k) for k, v in table.items() if v is None])
