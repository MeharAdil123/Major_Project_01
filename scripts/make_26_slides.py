import os
import pptx
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def build_presentation():
    prs = pptx.Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Theme Colors
    C_DARK_BG    = RGBColor(15, 23, 42)      # #0F172A Slate 900
    C_CARD_BG    = RGBColor(255, 255, 255)  # White
    C_LIGHT_BG   = RGBColor(248, 250, 252)  # #F8FAFC Slate 50
    C_PRIMARY    = RGBColor(13, 148, 136)   # #0D9488 Teal 600
    C_SECONDARY  = RGBColor(30, 41, 59)     # #1E293B Slate 800
    C_TEXT_DARK  = RGBColor(15, 23, 42)     # #0F172A Slate 900
    C_TEXT_MUTED = RGBColor(100, 116, 139)  # #64748B Slate 500
    C_ACCENT     = RGBColor(16, 185, 129)   # #10B981 Emerald 500
    C_ALERT      = RGBColor(225, 29, 72)    # #E11D48 Rose 600
    C_CARD_BORDER= RGBColor(226, 232, 240)  # #E2E8F0 Slate 200

    def add_header(slide, title_text, category_text, speaker_text):
        # Top banner background
        top_box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.15))
        top_box.fill.solid()
        top_box.fill.fore_color.rgb = C_DARK_BG
        top_box.line.color.rgb = C_DARK_BG

        # Category
        cat_p = slide.shapes.add_textbox(Inches(0.8), Inches(0.12), Inches(8), Inches(0.3))
        tf = cat_p.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = category_text.upper()
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = C_PRIMARY

        # Title
        title_p = slide.shapes.add_textbox(Inches(0.8), Inches(0.38), Inches(9.2), Inches(0.65))
        tf2 = title_p.text_frame
        tf2.word_wrap = True
        p2 = tf2.paragraphs[0]
        p2.text = title_text
        p2.font.size = Pt(20)
        p2.font.bold = True
        p2.font.color.rgb = RGBColor(255, 255, 255)

        # Speaker Badge
        badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(10.5), Inches(0.32), Inches(2.2), Inches(0.5))
        badge.fill.solid()
        badge.fill.fore_color.rgb = C_SECONDARY
        badge.line.color.rgb = C_PRIMARY
        badge.line.width = Pt(1.5)
        btf = badge.text_frame
        bp = btf.paragraphs[0]
        bp.text = speaker_text
        bp.font.size = Pt(11)
        bp.font.bold = True
        bp.font.color.rgb = RGBColor(255, 255, 255)
        bp.alignment = PP_ALIGN.CENTER

    def add_card(slide, left, top, width, height, title="", border_color=C_CARD_BORDER, bg_color=C_CARD_BG):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        card.line.color.rgb = border_color
        card.line.width = Pt(1)

        if title:
            tb = slide.shapes.add_textbox(Inches(left + 0.2), Inches(top + 0.15), Inches(width - 0.4), Inches(0.4))
            tf = tb.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = title
            p.font.size = Pt(13)
            p.font.bold = True
            p.font.color.rgb = C_SECONDARY
        return card

    def set_speaker_notes(slide, notes_text):
        slide.notes_slide.notes_text_frame.text = notes_text.strip()

    # =========================================================================
    # SLIDE 1: TITLE SLIDE
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = C_DARK_BG
    bg1.line.color.rgb = C_DARK_BG

    itb = s1.shapes.add_textbox(Inches(1.0), Inches(0.6), Inches(11.3), Inches(0.5))
    itf = itb.text_frame
    ip = itf.paragraphs[0]
    ip.text = "RNS INSTITUTE OF TECHNOLOGY, BENGALURU — DEPARTMENT OF ECE"
    ip.font.size = Pt(13)
    ip.font.bold = True
    ip.font.color.rgb = C_PRIMARY

    ttb = s1.shapes.add_textbox(Inches(1.0), Inches(1.1), Inches(11.3), Inches(1.8))
    ttf = ttb.text_frame
    ttf.word_wrap = True
    tp = ttf.paragraphs[0]
    tp.text = "Device-Free Human Activity Recognition & Fall Detection Using WiFi Channel State Information"
    tp.font.size = Pt(28)
    tp.font.bold = True
    tp.font.color.rgb = RGBColor(255, 255, 255)

    sub_p = ttf.add_paragraph()
    sub_p.text = "COTS ESP32-S3 Hardware • 200 Hz HT40 Link • Rigorous LOSO Cross-Validation • Real-Time Engine"
    sub_p.font.size = Pt(15)
    sub_p.font.color.rgb = C_TEXT_MUTED

    # Team Card
    tc = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(3.2), Inches(6.8), Inches(3.6))
    tc.fill.solid()
    tc.fill.fore_color.rgb = C_SECONDARY
    tc.line.color.rgb = C_PRIMARY
    tt_tb = s1.shapes.add_textbox(Inches(1.3), Inches(3.4), Inches(6.2), Inches(3.2))
    ttf = tt_tb.text_frame
    p = ttf.paragraphs[0]
    p.text = "PROJECT GROUP 10 (2026-2027)"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = C_PRIMARY

    members = [
        ("01", "Md Mehar Adil D H", "1RN23EC094"),
        ("02", "Mohith Gowda M", "1RN23EC095"),
        ("03", "Nihar Gowda", "1RN23EC106"),
        ("04", "Sujal L G", "1RN23EC169")
    ]
    for num, name, usn in members:
        mp = ttf.add_paragraph()
        mp.text = f"• {name}  [{usn}]"
        mp.font.size = Pt(13)
        mp.font.color.rgb = RGBColor(255, 255, 255)

    # Advisory Card
    gc = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.2), Inches(3.2), Inches(4.1), Inches(3.6))
    gc.fill.solid()
    gc.fill.fore_color.rgb = C_SECONDARY
    gc.line.color.rgb = C_CARD_BORDER
    gt_tb = s1.shapes.add_textbox(Inches(8.4), Inches(3.4), Inches(3.7), Inches(3.2))
    gtf = gt_tb.text_frame
    gp = gtf.paragraphs[0]
    gp.text = "ACADEMIC ADVISORY"
    gp.font.size = Pt(13)
    gp.font.bold = True
    gp.font.color.rgb = C_PRIMARY

    p1 = gtf.add_paragraph()
    p1.text = "\nProject Guide:"
    p1.font.size = Pt(11)
    p1.font.color.rgb = C_TEXT_MUTED
    p2 = gtf.add_paragraph()
    p2.text = "Dr. Leena Chandrashekar"
    p2.font.size = Pt(13)
    p2.font.bold = True
    p2.font.color.rgb = RGBColor(255, 255, 255)
    p2_sub = gtf.add_paragraph()
    p2_sub.text = "Associate Professor, Dept. of ECE"
    p2_sub.font.size = Pt(10)
    p2_sub.font.color.rgb = C_TEXT_MUTED

    p3 = gtf.add_paragraph()
    p3.text = "\nProject Reviewer:"
    p3.font.size = Pt(11)
    p3.font.color.rgb = C_TEXT_MUTED
    p4 = gtf.add_paragraph()
    p4.text = "Dr. Srikanth G N"
    p4.font.size = Pt(13)
    p4.font.bold = True
    p4.font.color.rgb = RGBColor(255, 255, 255)
    p4_sub = gtf.add_paragraph()
    p4_sub.text = "Associate Professor, Dept. of ECE"
    p4_sub.font.size = Pt(10)
    p4_sub.font.color.rgb = C_TEXT_MUTED

    set_speaker_notes(s1, """
Good morning respected examiners, guide, and faculty members. Welcome to our final-year major project presentation: 'Device-Free Human Activity Recognition and Fall Detection Using WiFi Channel State Information'.
Our team comprises Md Mehar Adil, Mohith Gowda, Nihar Gowda, and Sujal L G from the Department of Electronics and Communication Engineering at RNS Institute of Technology, under the expert guidance of Dr. Leena Chandrashekar and review of Dr. Srikanth G N.
In this work, we present an end-to-end, privacy-preserving sensing system built entirely with low-cost commodity microcontrollers, operating without cameras or wearables, evaluated under rigorous subject-independent standards.
""")

    # =========================================================================
    # SLIDE 2: MOTIVATION & PROBLEM STATEMENT
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    add_header(s2, "Motivation & Problem Statement: The Case for WiFi CSI", "Introduction & Context", "Speaker 1")

    # Card 1: Camera Limitations
    add_card(s2, 0.8, 1.4, 3.6, 5.6, "1. Camera-Based Vision Systems")
    tb1 = s2.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(3.2), Inches(4.7))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "Major Drawbacks:"
    p.font.bold = True
    p.font.size = Pt(12)
    p.font.color.rgb = C_ALERT
    b1 = [
        "Severe privacy invasion in private domestic spaces (bathrooms, bedrooms).",
        "Strict line-of-sight requirement; completely blocked by walls and smoke.",
        "Fails in low-light, darkness, or intense optical glare.",
        "High compute bandwidth required for continuous high-res video streaming."
    ]
    for b in b1:
        bp = tf1.add_paragraph()
        bp.text = f"• {b}"
        bp.font.size = Pt(10.5)

    # Card 2: Wearables Limitations
    add_card(s2, 4.8, 1.4, 3.6, 5.6, "2. Wearable Sensor Nodes")
    tb2 = s2.shapes.add_textbox(Inches(5.0), Inches(2.0), Inches(3.2), Inches(4.7))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "Major Drawbacks:"
    p.font.bold = True
    p.font.size = Pt(12)
    p.font.color.rgb = C_ALERT
    b2 = [
        "Requires active user compliance and routine battery replenishment.",
        "Elderly adults and dementia patients frequently forget or remove devices.",
        "Removed during sleep or bathing (where over 60% of senior falls occur!).",
        "Skin irritation, discomfort, and risk of loss/damage."
    ]
    for b in b2:
        bp = tf2.add_paragraph()
        bp.text = f"• {b}"
        bp.font.size = Pt(10.5)

    # Card 3: Proposed Solution
    add_card(s2, 8.8, 1.4, 3.7, 5.6, "3. Proposed WiFi-CSI Sensing", border_color=C_PRIMARY)
    tb3 = s2.shapes.add_textbox(Inches(9.0), Inches(2.0), Inches(3.3), Inches(4.7))
    tf3 = tb3.text_frame
    tf3.word_wrap = True
    p = tf3.paragraphs[0]
    p.text = "Core Engineering Advantages:"
    p.font.bold = True
    p.font.size = Pt(12)
    p.font.color.rgb = C_PRIMARY
    b3 = [
        "100% Privacy-Preserving: Captures zero optical or acoustic images.",
        "Through-Obstacle Penetration: 2.4 GHz RF penetrates non-metallic partitions.",
        "Device-Free: Operates completely contactlessly; user wears zero hardware.",
        "Ultra-Low Cost: Built on commodity ESP32 hardware (~$15 total).",
        "Dual-Use Infrastructure: Leverages ubiquitous ambient wireless fields."
    ]
    for b in b3:
        bp = tf3.add_paragraph()
        bp.text = f"• {b}"
        bp.font.size = Pt(10.5)

    set_speaker_notes(s2, """
Speaker 1: Every year, one out of three adults over age 65 experiences a fall, with delayed medical assistance dramatically worsening mortality. While cameras offer high fidelity, they represent a severe privacy invasion in bedrooms and restrooms where the majority of falls occur. Furthermore, wearables suffer from severe compliance fatigue—elderly users frequently forget to charge or wear them.
Our proposed solution utilizes ambient Wi-Fi Channel State Information. RF signals permeate indoor space, bouncing off human bodies. By measuring how these multipath reflections modulate the physical channel, we achieve device-free, 100% privacy-preserving fall and activity detection at ultra-low hardware cost.
""")

    # We will build all 26 slides programmatically
    slides_data = [
        # Slide 3: RF Physics
        ("RF Physics & CSI Fundamentals: Physical Principle & Multipath", "RF Physical Layer", "Speaker 1",
         [("OFDM Channel Estimation Model", "Frequency-Domain Channel Response", [
             "In 802.11n OFDM, the received symbol Y(f,t) relates to transmitted symbol X(f,t) via:",
             "Y(f, t) = H(f, t) · X(f, t) + N(f, t)   ==>   H(f, t) = Y(f, t) / X(f, t)",
             "H(f,t) is the complex Channel Frequency Response (CFR), estimated across subcarriers from known Long Training Field (LTF) symbols in every packet preamble."
         ]),
          ("Multipath Superposition & Motion", "Constructive / Destructive Interference", [
             "H(f,t) = H_static(f) + H_dynamic(f, t) = sum of L physical propagation paths.",
             "Static paths reflect off walls, floor, and metal cabinets; dynamic path reflects off moving limbs.",
             "Doppler Shift: f_D = (1 / λ) · (d/dt)[d_dynamic(t)]. At 2.462 GHz, λ ≈ 12.2 cm.",
             "Sub-Centimeter Sensitivity: Moving a body by λ/4 ≈ 3 cm flips the reflected phase by 180°.",
             "CSI vs RSSI: RSSI is a single coarse scalar power value; CSI provides fine-grained complex measurements across 114 subcarriers simultaneously."
         ])],
         """Speaker 1: Let us examine the RF physical principles. In OFDM communications, data is transmitted across orthogonal subcarriers. The channel frequency response H is estimated from the Long Training Field.
H represents the vector sum of static room reflections plus dynamic human reflections. Because the wavelength of 2.4 GHz Wi-Fi is approximately 12.2 cm, moving a limb by just 3 cm alters the round-trip reflection by half a wavelength, completely flipping the interference from constructive to destructive. Unlike RSSI, which is a crude, single-number summary prone to severe fading, CSI gives us 114 separate subcarrier measurements simultaneously."""
        ),

        # Slide 4: Hardware Setup
        ("Experimental Hardware Architecture & Library Testbed Layout", "Hardware Implementation", "Speaker 1",
         [("Hardware Component Architecture", "Off-The-Shelf Transceivers", [
             "Transmitter (TX): NodeMCU-32S (ESP-WROOM-32U, Xtensa LX6 @ 240 MHz).",
             "TX Antenna: External 8 dBi directional patch antenna mounted at height h = 0.9 m at (0.0, 0.0) m.",
             "Receiver 1 (RX1): YD-ESP32-S3 (Xtensa LX7 @ 240 MHz) + 6 dBi omni antenna at h = 1.0 m at (-1.3, 4.5) m.",
             "Receiver 2 (RX2): YD-ESP32-S3 + 6 dBi omni antenna at h = 0.5 m at (+1.3, 4.5) m.",
             "Host Node: Linux laptop (Intel i3-7020U, 7 GB RAM) receiving serial streams at 2,000,000 baud."
         ]),
          ("Room Geometry: College Library Hall", "Coordinate Frame (position_map.yaml v2)", [
             "Room: College Library Main Hall (active sensing area: 4.5 m x 5.0 m).",
             "Chair A: (-0.9, 3.2) m — sits directly on the direct RX1 line-of-sight link.",
             "Chair B: (+1.0, 1.5) m — sits directly on the direct RX2 line-of-sight link.",
             "Chair C: (0.0, 1.2) m — central chair positioned near the transmitter.",
             "Mattress M: Bounded area x in [-0.5, 1.5], y in [2.9, 3.8] m (all simulated falls performed here).",
             "Path 1 (Vertical): Walk along the LoS link (x = -1.5, y in [1.2, 4.0]).",
             "Path 2 (Horizontal): Walk across the LoS link (y = 2.55, x in [-2.0, 2.0])."
         ])],
         """Speaker 1: Moving to our physical hardware architecture. We selected COTS ESP32-S3 microcontrollers due to their native USB-Serial-JTAG and dual-core capabilities.
Our transmitter uses an ESP-WROOM-32U paired with an 8 dBi directional patch antenna mounted at 0.9 m, beaming energy across the room.
On the receiving side, we deploy two ESP32-S3 boards with 6 dBi omni whip antennas at different elevations—RX1 at 1.0 m and RX2 at 0.5 m.
The testbed was established in our college library hall. The mattress for simulated falls was placed at zone M, chairs were placed at spots A, B, and C, and two distinct walking trajectories were marked: Path 1 along the radio link, and Path 2 bisecting across it."""
        ),

        # Slide 5: Radio Layer & Firmware Protocol
        ("Radio Layer Specifications & Binary Wire Framing Protocol", "Firmware & Protocol", "Speaker 1",
         [("Radio Layer Physical Parameters", "IEEE 802.11n Configuration", [
             "Bandwidth / Channel: Wi-Fi Channel 11 (2462 MHz), HT40 mode (40 MHz width, 2432–2472 MHz).",
             "PHY Rate: Fixed to MCS0 (BPSK, 1/2 code rate) with Long Guard Interval (800 ns). Zero rate adaptation.",
             "Packet Transmission Rate: Exactly 200 Hz (5000 µs hardware esp_timer interrupt period).",
             "TX Output Power: Configured at 5 dBm (CONFIG_TX_POWER_QDBM = 20), saved in NVS (D-017, D-029).",
             "Transmission Mode: Connectionless ESP-NOW broadcast with static radio_id = 0xCBD36978."
         ]),
          ("Wire Protocol v2 Framing", "High-Throughput Serial Streaming", [
             "Frame Format: 48-byte packed C-struct header framed by sync bytes 0xA5 0x5A.",
             "Data Integrity: Protected by CRC-16/CCITT-FALSE across header and payload bytes.",
             "Active Carriers: 384 raw CSI bytes per packet representing HT-LTF I/Q values.",
             "Audit Verification: Decoded 250 files across 125 morning takes with ZERO CRC errors (D-011 limit < 0.5%).",
             "Board Liveness: Firmware v2.1 introduces task watchdog and boot reset reasons in HELLO frames."
         ])],
         """Speaker 1: On the firmware layer, stability is paramount. We compiled custom ESP-IDF v5.5.5 firmware. We locked the PHY layer to 802.11n HT40 on Channel 11 with fixed MCS0 modulation and Long Guard Interval, transmitting connectionless broadcast packets at precisely 200 Hz via a hardware timer.
To stream this high-speed data across USB to the host, we engineered Wire Protocol v2. Packets are framed with sync words 0xA5 0x5A and guarded by CRC-16 checksums. In our raw data audit of 250 binary files, we verified exactly zero CRC errors, proving robust, lossless serial ingestion at 2 Megabaud."""
        ),

        # Slide 6: Data Collection Protocol
        ("Data Collection Protocol, Safety Procedures & RF Hygiene", "Data Acquisition", "Speaker 2",
         [("Experimental Recording Protocol", "Controlled Script Execution", [
             "Acoustic Pacing: Automated terminal speech countdown ensured strict protocol synchronization.",
             "Event Takes (10 s): 3 s motionless baseline -> Spoken 'GO' prompt -> Action execution (1–2 s) -> 4 s settling posture.",
             "State Takes (30 s): Continuous, steady-state execution (sitting, standing, walking, lying, or empty).",
             "Fall Safety Mandate: All falls performed onto a high-density gymnasium mattress with spotters present.",
             "Action Look-Alikes: Included sit_down, stand_up, and bend_pick to challenge the fall detector."
         ]),
          ("RF Hygiene Protocol (Decision D-032)", "Eliminating In-Band Contention", [
             "The Contention Discovery: Link check before S5 revealed that leaving host laptop Wi-Fi active caused 41.5% packet loss on RX2 at strong RSSI (-38 dBm) due to local radio contention.",
             "Hygiene Rule Enforced: Host laptop onboard Wi-Fi and Bluetooth disabled via rfkill; all bystander smartphones switched to airplane mode.",
             "Impact: Disabling laptop radios instantly dropped packet loss to 1.1% on RX1 and 4.7% on RX2.",
             "Rule Codified: Made mandatory for all subsequent recording and live system operations."
         ])],
         """Speaker 2: I am Speaker 2, and I will cover data acquisition and signal processing.
To ensure clean data, we designed a disciplined recording protocol. Each event take lasted 10 seconds, synchronized by an automated speech countdown: 3 seconds of pre-cue stillness, an audible 'GO' command, the transition, and 4 seconds of post-action settling. For safety, all falls were performed onto an impact mattress.
Crucially, during bench testing, we made a vital discovery: leaving the laptop's own Wi-Fi enabled caused massive 41.5% packet loss on our receiver due to co-channel radio contention. Under Decision D-032, we enforced strict RF hygiene—shutting down laptop Wi-Fi and Bluetooth and enforcing airplane mode on phones, instantly slashing packet loss down to 1–4%."""
        ),

        # Slide 7: Dataset Audit
        ("The Curated Dataset & Phase 0 Audit: 202 Takes Across 6 Folds", "Dataset & Audit", "Speaker 2",
         [("Final Dataset Composition", "202 Recorded Takes (801 Files Total)", [
             "Cohort: 6 healthy adult volunteers (S1 to S6) + unoccupied room takes (none).",
             "Morning Session (S1–S4): 125 takes (118 subject takes + 4 baseline empty takes).",
             "Afternoon Session (S5–S6): 77 takes recorded after an intentional transmitter realignment.",
             "Activity Breakdown: 42 falls, 43 sit-downs, 46 stand-ups, 20 bend-and-picks, 16 walks, 11 stands, 11 sits, 6 lies, 7 empty.",
             "Format 2 Windows: Exactly 2401 windows of 4 s extracted (hop 0.5 s, 20% quality gate)."
         ]),
          ("Session Effect & Audit Findings", "Phase 0 Read-Only Audit (docs/AUDIT.md)", [
             "Audit Immutability: Scripts read data/raw as read-only; 801 files verified by SHA-256 manifest.",
             "Take Overrides (D-018): S1_T29_walk was marked invalid due to operator abort; decoded data was intact and overridden via config/take_overrides.csv without editing raw meta.json.",
             "Session Drift (D-033): S5/S6 show no RSSI drift (≤ 1.0 dB shift), but static channel shape shifted 3.4–4.4 dB RMS between morning and afternoon sessions due to TX re-aim.",
             "Evaluation Impact: S5 and S6 represent true cross-session test folds."
         ])],
         """Speaker 2: Our curated dataset comprises 202 takes and over 800 files, spanning 6 volunteers and 8 distinct activities plus empty room takes. 
In Phase 0, we conducted a rigorous read-only cryptographic audit of every raw file. We found that morning takes for S1 through S4 and afternoon takes for S5 and S6 were completely intact. 
However, because the transmitter was realigned between sessions, the static channel profile shifted by 3.4 to 4.4 dB RMS between morning and afternoon. This means S5 and S6 serve as true cross-session evaluation folds, providing an honest test of whether models can handle environmental shifts."""
        ),

        # Slide 8: DSP Subcarrier Architecture
        ("DSP Pipeline: Subcarrier Layout, Sequence Alignment & Gap-Fill", "Digital Signal Processing", "Speaker 2",
         [("Active HT-LTF Subcarriers", "114 Used Subcarriers Verified", [
             "802.11n 40 MHz Channel Layout: 128 total subcarrier bins in FFT.",
             "Active Energy Carriers: Verified empirically across 396 receiver takes:",
             "k in [-58, -2] and [+2, +58]  ==>  Exactly 114 active subcarriers.",
             "Null Subcarriers: DC carrier (bin 0, ±1) and guard bands ([-64..-59] and [+59..+63]) carry zero signal.",
             "L-LTF Bins: Evaluated in Phase 2; confirmed to occupy upper 20 MHz only. Dropped to focus on 114 HT-LTF."
         ]),
          ("Packet Synchronization & Linear Gap-Fill", "Phasor-Domain Interpolation", [
             "Sequence Alignment: RX1 and RX2 streams are aligned by the TX sequence number embedded in firmware.",
             "Linear Gap-Fill: Missing packets within acceptable burst limits are reconstructed via linear interpolation across the complex phasor domain.",
             "Quality Gate (D-039): A window is rejected if either receiver suffers > 20% missing packets or any single gap exceeds 100 ms (20 packets).",
             "Diagnostic Impact: Relaxing initial strict 10% gate to 20% reduced window drops from 27.8% down to 3.9%, recovering 67% of S1's otherwise lost data without distorting DSP."
         ])],
         """Speaker 2: Now let us examine our digital signal processing pipeline. First, we verified the active subcarrier architecture on our hardware. While the theoretical 40 MHz FFT contains 128 bins, physical energy is transmitted strictly across 114 active subcarriers—bins -58 to -2 and +2 to +58—with DC and guard bands remaining null.
Next, packets from RX1 and RX2 are synchronized using the TX sequence counter. Any missing packets are linearly interpolated in the complex phasor domain. Importantly, our diagnostic analysis in Decision D-039 showed that a rigid 10% packet loss gate discarded 28% of valid windows due to momentary body shadowing; relaxing this gate to 20% dropped rejections to 3.9% while preserving signal fidelity."""
        ),

        # Slide 9: DSP Filtering & Gain Scaling
        ("DSP Pipeline: FIR Anti-Aliasing, Decimation & Gain Steps", "Digital Signal Processing", "Speaker 2",
         [("Anti-Aliasing FIR Decimation", "Suppressing High-Frequency Out-Of-Band Noise", [
             "Human Kinetic Limits: Normal human body motion generates Doppler shifts bounded below 30–40 Hz (v ≈ 2 m/s, f_D ≈ 32.8 Hz).",
             "Anti-Alias FIR Filter: 27-tap linear-phase Equiripple low-pass filter (passband 0–35 Hz, -45 dB stopband attenuation at 50 Hz).",
             "Decimation: Downsampled from raw 200 Hz to 100 Hz, eliminating high-frequency serial noise and spectral folding.",
             "Phase Coherence: Linear-phase FIR design introduces constant group delay without phase distortion."
         ]),
          ("Resolving 6.1 dB Automatic CSI Gain Steps", "Physics of ESP-IDF AGC Steps (D-035)", [
             "The Symptom: CSI amplitude exhibited alternating 6.1 dB power drops uncorrelated with RSSI, heavily concentrated at Chair B.",
             "Root Cause: ESP32-S3 internal automatic CSI scaling (manu_scale = false) halving int8 digital resolution under high signal levels.",
             "The Fix: Per-packet gain normalization divides each subcarrier by the packet's mean amplitude:",
             "X_norm(k, t) = X_raw(k, t) / [ (1/114) * sum_i(X_raw(i, t)) ]",
             "Integrity Rule: Low-scale packet fraction is permanently banned as a feature (correlates with Chair B position)."
         ])],
         """Speaker 2: To prepare the signal for feature extraction, two critical DSP stages were implemented. First, because human motion does not exceed 35 Hz Doppler frequencies, we passed the 200 Hz signal through a 27-tap anti-aliasing FIR filter and decimated it to 100 Hz, removing high-frequency noise without distortion.
Second, we discovered that the ESP32 internal Automatic Gain Control caused abrupt 6.1 dB amplitude drops across consecutive packets! This was a hardware scaling artifact. We resolved it by applying per-packet mean normalization, completely removing the artificial step discontinuities while banning the low-scale packet fraction from being used as a feature."""
        ),

        # Slide 10: Complex Phase Sanitization
        ("DSP Pipeline: Subcarrier Phase Unwrapping & Sanitization", "Digital Signal Processing", "Speaker 2",
         [("The Raw Phase Problem", "Carrier Frequency & Packet Delay Noise", [
             "Raw Phase Instability: Raw phase angles exhibit uniform random distribution across packets (circular std ≈ 2.82 rad).",
             "Sources of Corruption: Caused by Carrier Frequency Offset (CFO), Sampling Frequency Offset (SFO), and microsecond Packet Detection Delays (PDD).",
             "Equation of Corruption: θ_raw(k, t) = θ_true(k, t) - 2π · k · Δt / N + β + Z_noise."
         ]),
          ("Two-Stage Linear Sanitization (Decision D-036)", "Subcarrier Unwrapping & Detrending", [
             "Stage 1: Frequency Unwrapping across subcarriers: θ_unwrap(k, t) = unwrap(θ_raw(k, t)).",
             "Stage 2: Least-Squares Linear Detrending to remove slope α_t and intercept β_t for each individual packet:",
             "θ_sanitized(k, t) = θ_unwrap(k, t) - (α_t · k + β_t)",
             "Quantitative Noise Reduction: Sanitized phase circular standard deviation collapses from 2.82 rad down to 0.13–0.16 rad!",
             "Physical Utility: Unveils path-length variations; dynamic phase features weighted by amplitude squared to neutralize 2π slips."
         ])],
         """Speaker 2: Raw Wi-Fi phase is notoriously corrupted by hardware synchronization errors, appearing as pure random noise with a circular standard deviation of 2.82 radians.
To extract physical path-length changes, we built a two-stage phase sanitizer under Decision D-036. We first unwrap the phase across the 114 subcarriers, and then perform least-squares linear detrending on every packet to subtract the random slope and offset.
This mathematical sanitization reduced the phase noise floor to just 0.14 radians, allowing us to capture fine-grained human chest and limb movements."""
        ),

        # Slide 11: The Position Confound
        ("The Spatial Leakage Trap: Discovering the Position Confound", "Experimental Rigor", "Speaker 2",
         [("The Hidden Experimental Trap", "Why Standard ML Pipelines Cheat", [
             "Spatial Confounding (D-024): In home monitoring, actions naturally correlate with furniture (falls on mattress, sitting at chairs, walking on paths).",
             "Body Shadowing Effect: Sitting at Chair A shadows RX1; sitting at Chair B shadows RX2.",
             "The Leakage: Static features (mean RSSI, static subcarrier band amplitudes) encode WHERE a person is rather than WHAT action is occurring.",
             "The Academic Fallacy: Published papers using static features achieve 95% accuracy because the model simply memorizes room coordinates."
         ]),
          ("Our Architectural Solution: Static vs. Dynamic Split", "Enforcing Genuine Kinematic Sensing", [
             "Bifurcated Feature Architecture: Every feature explicitly classified into Static (Spatial) or Dynamic (Kinematic) groups.",
             "Mandatory Dynamic-Only Reporting: All primary event models are trained strictly on dynamic motion features (temporal variance, Doppler powers).",
             "Empirical Proof of Confound: Static features alone drop event macro-F1 to 0.353; identical sit-down actions at Chair A achieved 76% recall, but collapsed to 25% at Chair B where 16–22% were mistaken for falls!",
             "Rigorous Reporting: Position confounding documented as a first-class project limitation in REPORT.md."
         ])],
         """Speaker 2: This slide highlights our most critical methodological contribution: discovering and tackling the Position Confound under Decision D-024.
In any indoor environment, activities are physically tied to furniture. A human body sitting at Chair A shadows Receiver 1, creating a unique static frequency attenuation. If you feed raw amplitudes or RSSI into a machine learning model, it achieves 95% accuracy—not by recognizing the physical action of sitting, but by memorizing the location of Chair A!
To prevent this artificial inflation, we bifurcated our feature space, stripping static levels out of our event classifiers and forcing them to train on dynamic Doppler motion alone."""
        ),

        # Slide 12: Feature Engineering
        ("Feature Engineering: The 83-Dimensional f2 Feature Space", "Feature Engineering", "Speaker 2",
         [("Static Spatial Group (33 Features)", "Captures Static Multipath Profile", [
             "Band Mean Amplitudes (16): Normalized mean amplitude across 8 subcarrier sub-bands for RX1 and RX2.",
             "Received Power Levels (3): Mean RSSI for RX1, RX2, and cross-receiver spatial difference (RX1 - RX2).",
             "Spatial PCA Loadings (14): Explained variance ratios of top 3 principal components and carrier quarter loadings.",
             "Utility: Used for baseline presence detection; excluded from dynamic event classification."
         ]),
          ("Dynamic Motion Group (50 Features — Primary Input)", "Captures Doppler Kinematics", [
             "Temporal Fluctuations (12): Standard deviation and 10 ms absolute differences across subcarriers (RX1/RX2).",
             "Sliding Motion Energy (8): 0.25 s sliding standard deviation of PC1–3 and temporal peak location.",
             "Doppler Spectral Bandpowers (12): FFT bandpowers of PC1: sway (< 1 Hz), walking (1–3 Hz), and fall impact (> 3 Hz).",
             "Inter-Carrier Coherence (2): Mean correlation across subcarrier fluctuations; high coherence indicates macroscopic body movement.",
             "Sanitized Phase Dynamics (10): Amplitude-weighted circular variance and phase derivative energy.",
             "Cross-Receiver Dynamics (4): Log-ratios of temporal variance and cross-correlation of RX1/RX2 motion envelopes."
         ])],
         """Speaker 2: Our feature space, version f2, contains 83 mathematically defined features extracted per 4-second window.
Thirty-three features represent static spatial characteristics, such as subcarrier band averages and RSSI spatial differences.
Fifty features represent pure dynamic kinematics: temporal standard deviations, 0.25-second sliding motion energy, FFT Doppler bandpowers isolating walking strides from high-frequency fall impacts, subcarrier coherence, and amplitude-weighted phase dynamics.
This feature set captures the full temporal, spectral, spatial, and phase profile of human movements."""
        ),

        # Slide 13: LOSO Evaluation
        ("Evaluation Methodology: Leave-One-Subject-Out (LOSO)", "Evaluation Framework", "Speaker 3",
         [("Why Random Cross-Validation Fails", "Eliminating Subject Data Leakage", [
             "The Random Split Flaw: Shuffling windows randomly into 80/20 train/test leaks identical subject multipath and clothes reflections into both splits.",
             "The LOSO Standard: Evaluation is conducted strictly via 6-Fold Leave-One-Subject-Out (LOSO) cross-validation across all subjects S1 to S6.",
             "Complete Isolation: In each fold, all takes from one volunteer are completely withheld from training and used strictly as test data.",
             "Round-Robin Baselines: The 7 empty-room takes are distributed round-robin across folds (D-028) so every fold maintains true negative presence examples."
         ]),
          ("Nested Hyperparameter Tuning", "Zero Test Fold Contamination", [
             "Nested Search: Within each outer training fold, hyperparameter optimization uses GroupKFold(n_splits=3) grouped by training subjects.",
             "Feature Scaling: StandardScaler fitted strictly on training fold distributions; test fold transformed without leakage.",
             "Scoring Metric: Macro-averaged F1-score across folds (Mean ± Std).",
             "Reporting Standard: Deep models evaluated across 3 random seeds per fold to guarantee statistical repeatability."
         ])],
         """Speaker 3: I am Speaker 3, and I will present our modeling benchmarks, optimization, and fall alarm chain.
In machine learning research, how you evaluate determines whether your results are real or an illusion. Random 80/20 train-test splits suffer from fatal data leakage because windows from the same person end up on both sides of the split.
We enforced strict 6-Fold Leave-One-Subject-Out cross-validation. When evaluating on Subject 1, all data from Subject 1 is completely locked away. Furthermore, all feature scaling and hyperparameter grids were tuned using nested cross-validation strictly inside the remaining training subjects, guaranteeing zero test set contamination."""
        ),

        # Slide 14: Window Length Optimization
        ("Temporal Window Length Optimization: 2 s vs 3 s vs 4 s", "Model Optimization", "Speaker 3",
         [("Objective Optimization Rule", "Pre-Registered Selection Metric (D-046)", [
             "Window Selection Rule: Average LOSO macro-F1 across presence, state, and event tasks using dynamic features.",
             "Evaluated Lengths: 2.0 s, 3.0 s, and 4.0 s sliding windows with 0.5 s step hop.",
             "2-second Windows: Score = 0.533 (Events: 0.450, State: 0.563, Presence: 0.585).",
             "3-second Windows: Score = 0.582 (Events: 0.503, State: 0.580, Presence: 0.665).",
             "4-second Windows: Score = 0.603 (Events: 0.539, State: 0.572, Presence: 0.698)  ==>  WINNER (4 s Adopted)."
         ]),
          ("Physical Kinematic Justification", "Capturing the Anatomy of a Fall", [
             "Anatomy of a Fall: A human fall consists of: (1) Pre-fall loss of balance, (2) Rapid downward descent (0.5–1.0 s), (3) Floor impact shock, and (4) Post-fall motionless immobility.",
             "Window Sizing Physics: A 2 s window truncates either the initial descent or post-fall stillness.",
             "The 4 s Advantage: A 4 s window captures the entire transition from standing motion to impact to lying prone.",
             "Latency Trade-off: While 4 s introduces slightly longer window latency, a 0.5 s hop rate ensures the live engine refreshes predictions every 500 ms."
         ])],
         """Speaker 3: Choosing the time window duration is a critical engineering decision. Under Decision D-046, we formulated a pre-registered optimization rule: compute the average macro-F1 across all three tasks under 2-second, 3-second, and 4-second windows.
The benchmark yielded 0.533 for 2 seconds, 0.582 for 3 seconds, and a winning 0.603 for 4 seconds.
Physically, this makes complete sense: a fall is not an instantaneous spike; it is a kinetic sequence comprising loss of balance, descent, ground impact, and subsequent stillness. A 4-second window captures this complete kinetic narrative, providing the classifiers with both the impact and post-fall stillness."""
        ),

        # Slide 15: Model Benchmarking Track A
        ("Model Benchmarking (Track A): Classical Machine Learning", "Model Comparison", "Speaker 3",
         [("Benchmark Results on 4 s Windows (Dynamic f2 Features)", "LOSO 6-Fold Performance Summary", [
             "Events (5 Classes: Fall, Sit, Stand, Bend, None):",
             "  • SVM-RBF (Dynamic f2): Macro-F1 = 0.539 ± 0.054 (Fall F1: 0.521, Fall Recall: 0.552).",
             "  • XGBoost (Dynamic f2): Macro-F1 = 0.523 ± 0.084 (Fall F1: 0.560, Fall Recall: 0.512).",
             "  • LightGBM / Extra Trees: Macro-F1 = 0.505 / 0.502.",
             "  • Random Forest Baseline: Macro-F1 = 0.486 ± 0.071.",
             "Postural State (4 Classes: Sit, Stand, Walk, Lie):",
             "  • Extra Trees (300 trees): Macro-F1 = 0.572 ± 0.115 (Best performing model).",
             "Presence Detection (2 Classes: Empty vs Occupied):",
             "  • Logistic Regression: Macro-F1 = 0.698 ± 0.065 (Sensitivity: 0.855, Specificity: 0.828)."
         ]),
          ("Analytical Observations", "Key Insights", [
             "Linear vs Kernel Boundaries: SVM with Radial Basis Function kernel excelled at complex dynamic event boundaries.",
             "Ensemble Robustness: Extra Trees outperformed single trees and standard RF on stationary postures.",
             "Cross-Session Stability: S5 and S6 afternoon folds achieved strong F1 (0.595 and 0.520 on SVM events), confirming dynamic features generalize across sessions."
         ])],
         """Speaker 3: Slide 15 presents our Track A classical machine learning benchmarks across all 6 folds on 4-second windows.
On the 5-class event task, SVM with an RBF kernel achieved the highest classical macro-F1 of 0.539 with a fall recall of 55.2%.
On the 4-class postural state task, Extra Trees achieved 0.572 macro-F1, outperforming standard Random Forests.
For presence detection, Logistic Regression achieved 0.698 macro-F1 with balanced 85.5% sensitivity and 82.8% specificity.
Notice that across afternoon folds S5 and S6, SVM-RBF maintained steady F1-scores of 0.595 and 0.520, confirming that dynamic features transfer across sessions."""
        ),

        # Slide 16: Track B vs Track C
        ("Benchmarking Track B (MiniRocket) vs Track C (Deep Neural Nets)", "Advanced Models", "Speaker 3",
         [("Track B: MiniRocket Transform", "NumPy Re-Implementation (D-043)", [
             "Architecture: 10,000 random convolutional kernels mapping 16 band channels at 100 Hz to pooled features with a Ridge Regression head.",
             "Events Macro-F1: 0.572 ± 0.062 (Rank 1 by selection rule D-047).",
             "Presence Macro-F1: 0.729 ± 0.178 (Highest raw mean, but high variance across folds).",
             "The MiniRocket Flaw: Poor window-level fall recall (0.434 vs 0.552 for SVM); uncalibrated ridge scores; high CPU inference latency (326 ms single-window)."
         ]),
          ("Track C: 10 Deep Learning Architectures", "Fixed Budget (AdamW, Patience 6, 3 Seeds)", [
             "Evaluated Models: 1D-CNN, CNN-LSTM, CNN-BiLSTM, BiLSTM, GRU, TCN, ResNet-1D, ABLSTM, THAT (Transformer). Model sizes: 19k to 127k parameters.",
             "Events Performance: Best deep model (CNN-BiLSTM) achieved only 0.344 ± 0.041 macro-F1.",
             "Remaining Architectures: Scored between 0.332 and 0.264 macro-F1.",
             "Outcome: Deep learning models severely underperformed classical tabular models by over 20% F1."
         ])],
         """Speaker 3: We also evaluated two advanced paradigms: Track B MiniRocket and Track C Deep Learning.
MiniRocket generated 10,000 random convolutional features directly from subcarrier bands, achieving 0.572 macro-F1 on events. However, MiniRocket suffered from lower fall recall (43.4%), produced uncalibrated linear scores, and required 326 ms of single-window latency on the laptop CPU.
In Track C, we benchmarked 10 deep architectures including ResNets, LSTMs, TCNs, and Transformers. Shockingly, the best deep network, a CNN-BiLSTM, achieved only 0.344 macro-F1, trailing classical SVMs by nearly 20%."""
        ),

        # Slide 17: Deep Learning Overfitting
        ("Why Deep Learning Failed: Empirical Loss Curves & Small Data", "Failure Analysis", "Speaker 3",
         [("The Overfitting Divergence", "Training vs. Validation Trajectories", [
             "Empirical Evidence: Recorded across all 10 architectures (results/phase4/track_c/*_curves.png).",
             "Training Loss: Rapidly plunged to ~0.2 within 5 epochs.",
             "Validation Loss: Diverged sharply upwards beginning as early as epoch 3!",
             "Early Stopping: Consistently triggered at median epochs 5 to 9 across all folds.",
             "Event Class Collapse: Deep models severely under-predicted transient events, exhibiting recalls between 0.10 and 0.40."
         ]),
          ("Physical Root Causes of Deep Failure", "Theoretical Lessons", [
             "Small Sample Regime: 2401 windows from 6 human subjects is insufficient to constrain 100,000+ deep neural parameters.",
             "Multipath Domain Shift: Deep networks memorized the static multipath scattering profiles of individual training subjects rather than generalizable body kinematics.",
             "Tabular Dominance: Physics-engineered features (Doppler power, phase circular variance) combined with max-margin classifiers (SVM) provide essential inductive bias.",
             "Scientific Honesty (D-048): Deep failure reported transparently as-run without post-hoc cherry-picking."
         ])],
         """Speaker 3: Slide 17 provides an honest post-mortem on why deep learning failed. Examining our loss curves, training loss plummeted to 0.2, but validation loss diverged upwards beginning at epoch 3.
Why? In Wi-Fi sensing, 2400 windows across 6 people is small data. Deep neural networks with 100,000 parameters have enough capacity to memorize the exact multipath reflections of individual subjects. When evaluated on an unseen subject, their representations collapsed.
Physics-grounded, handcrafted features with max-margin SVM classifiers provide the inductive bias necessary to generalize across human bodies on small datasets."""
        ),

        # Slide 18: Gate 4 Decisions
        ("Gate 4 Model Selection: Justifying Departures from the Rule", "Decision Register D-050", "Speaker 3",
         [("Adopted Final Production Models", "4 s Windows, Dynamic f2 Features", [
             "Events Task: SVM-RBF (C = 10, γ = 0.01) — Macro-F1: 0.539 ± 0.054.",
             "Postural State Task: Extra Trees (300 trees, max_feat = 0.3) — Macro-F1: 0.572 ± 0.115.",
             "Presence Task: Logistic Regression (C = 1.0) — Macro-F1: 0.698 ± 0.065.",
             "Fall Alarm Engine: Platt-Calibrated Binary SVM-RBF (C = 1.0, γ = 0.01)."
         ]),
          ("Why We Overruled MiniRocket (Decision D-050)", "Life-Safety & Real-Time Rationale", [
             "1. Fall Sensitivity Priority: MiniRocket achieved higher overall F1 (0.572 vs 0.539) by predicting common classes, but had POOR fall recall (0.434 vs 0.552 for SVM). For a fall alarm, missing falls is unacceptable.",
             "2. Probability Calibration: MiniRocket's ridge head outputs uncalibrated scores; SVM provides Platt-calibrated posterior probabilities P(fall) essential for threshold gating.",
             "3. Real-Time Latency: Single-window MiniRocket transform requires 326 ms on CPU; SVM inference requires < 1 ms on f2 features (total Predictor call = 67 ms with cached PCA), easily fitting inside 500 ms engine cycles.",
             "4. Presence Stability: MiniRocket collapsed on subjects S3 (0.474) and S4 (0.487); Logistic Regression was completely stable (± 0.065)."
         ])],
         """Speaker 3: At Gate 4, we established our final production models under Decision D-050. Our pre-fixed automated selection rule initially nominated MiniRocket for Events and Presence. However, we explicitly overruled it in favor of SVM-RBF and Logistic Regression for four concrete engineering reasons:
First, MiniRocket sacrificed fall detection sensitivity (43% vs 55% for SVM).
Second, MiniRocket outputs uncalibrated numbers, whereas an emergency alarm requires calibrated probabilities.
Third, MiniRocket required 326 ms of compute per window on our CPU, whereas SVM predicts in under 1 millisecond.
Finally, Logistic Regression provided rock-solid cross-subject presence stability, avoiding the collapse MiniRocket suffered on Subjects 3 and 4."""
        ),

        # Slide 19: Calibrated Fall Alarm Chain
        ("The Calibrated Fall Alarm Chain Architecture (Decision D-051)", "Fall Alarm Engineering", "Speaker 3",
         [("Continuous Stream Decision Chain", "Moving Beyond Isolated Window Testing", [
             "The Reality Gap: Testing isolated windows does not reflect reality. In real life, a streaming engine processes continuous overlapping windows.",
             "Binary Fall Detector: Dedicated Binary SVM-RBF (fall vs rest) with Platt (sigmoid) calibration fitted strictly on inner training folds.",
             "Nested Threshold Tuning: Threshold θ (0.30–0.95) and sliding window rule (k-of-n) optimized on inner training LOSO streams.",
             "Adopted Production Rule: Alarm triggered if ≥ 2 of the last 3 windows have P(fall) ≥ 0.50.",
             "Alarm Cooldown: 10-second lockout timer prevents duplicate burst alarms following an initial trigger."
         ]),
          ("Live = Offline Equivalence (Decision D-054)", "Zero Train/Serve Skew", [
             "Verification Test: Replayed 12 real takes packet-by-packet through the live buffer and compared outputs against the offline pipeline.",
             "Bit-Identical Result: Exact 0.00000 maximum absolute difference in features, X, P, and probabilities across all 378 real windows!",
             "Significance: Proves zero train-serve skew between laboratory Python code and production streaming runtime."
         ])],
         """Speaker 3: Testing isolated windows does not simulate a real-world emergency alarm. Under Decision D-051, we engineered a complete continuous streaming fall alarm chain.
We trained a dedicated binary SVM-RBF and applied Platt calibration strictly on inner training subjects to output true probabilities.
Using inner cross-validation, we optimized the decision logic: an alarm sounds if at least 2 out of the last 3 consecutive windows have P(fall) ≥ 0.50, backed by a 10-second cooldown timer.
Furthermore, under Decision D-054, we proved that our live streaming engine and offline training code produce bit-identical numbers across 378 real windows, eliminating train-serve skew."""
        ),

        # Slide 20: Stream Fall Alarm Results
        ("Fall Detection Stream Performance: Evaluating the Full Chain", "Empirical Evaluation", "Speaker 3",
         [("Continuous Stream Benchmark Results", "Tested on All 202 Real Takes (2401 Windows)", [
             "Metric | Baseline 5-Class SVM (θ=0.6, 2-of-3) | Adopted Calibrated Chain (D-051)",
             "--------------------------------------------------------------------------------",
             "Falls Detected           | 18 of 42 (42.9%)              | 21 of 42 (50.0%)",
             "Look-Alike False Alarms  | 9 of 109 takes (8.3%)         | 8 of 109 takes (7.3%)",
             "Walking False Alarms     | 45.4 / hour (6 in 0.132 h)    | 30.3 / hour (4 in 0.132 h)",
             "Still-Take False Alarms  | 3.2 / hour (1 in 0.314 h)     | 6.4 / hour (2 in 0.314 h)",
             "Median Trigger Latency   | 2.05 s post-onset             | 1.99 s post-onset"
         ]),
          ("Detailed Take-Level Breakdown", "Per-Fold Performance & Caveats", [
             "Per-Fold Falls Caught: S1: 2/8, S2: 2/5, S3: 4/5, S4: 3/8, S5: 5/8, S6: 5/8 (Total: 21/42).",
             "Look-Alike False Alarms: 5 in sit_down, 3 in stand_up, 0 in bend_pick.",
             "Honest Engineering Reality: Catching 50% of falls with a 7.3% look-alike false alarm rate and 30 walking alarms/hour demonstrates proof-of-concept feasibility, but confirms the system is not yet a clinical medical device."
         ])],
         """Speaker 3: Slide 20 presents our stream evaluation across all 202 takes.
Our calibrated binary chain caught 21 of 42 simulated falls (50%), improving upon the 5-class baseline of 18 falls.
Crucially, look-alike false alarms were limited to 7.3% (8 out of 109 takes), with zero false alarms during bend-and-pick actions. Walking false alarms were reduced from 45 to 30 alarms per hour, with a rapid detection latency of 1.99 seconds.
Our honest conclusion: the system catches half of simulated falls and resists everyday look-alikes, but walking false alarms and missed falls confirm that further engineering is required before clinical use."""
        ),

        # Slide 21: Ablations
        ("Systematic Ablation Studies: What Drives Physical Sensing?", "Ablation Analysis", "Speaker 3",
         [("Feature & Sensor Ablations (Events Task, SVM-RBF, 4 s)", "Macro-F1 Performance Impact", [
             "Ablation Condition | Macro-F1 | Delta vs Reference | Physical Meaning",
             "---------------------------------------------------------------------------------",
             "Dynamic Reference  | 0.539    | Reference         | All 50 dynamic f2 features",
             "Static Only        | 0.353    | -0.186            | Static profiles fail completely",
             "RX1 Only (Upper)   | 0.384    | -0.155            | Loses spatial diversity",
             "RX2 Only (Lower)   | 0.403    | -0.136            | Loses link diversity",
             "Minus Motion Energy| 0.474    | -0.065            | Motion energy is top feature",
             "Minus Bandpowers   | 0.494    | -0.045            | Doppler spectrum is critical",
             "Minus Phase        | 0.527    | -0.012            | Sanitized phase adds boost",
             "Amplitude Only     | 0.535    | -0.004            | Phase helps slightly on events"
         ]),
          ("Key Physical Insights", "Core Takeaways", [
             "Dual Antennas are Mandatory: Dropping either receiver collapses F1 from 0.539 to ~0.39. Two spatial vantage points are essential to overcome human body shadowing.",
             "Doppler & Energy Dominate: Motion energy and FFT bandpowers carry over 70% of discriminatory event information.",
             "Phase Utility: Phase adds minor gains (+0.012) to events, but substantial stability (+0.039) to presence."
         ])],
         """Speaker 3: To understand the physical drivers of our system, we conducted extensive ablations.
First: Dual receivers are mandatory. Removing either receiver drops event macro-F1 from 0.539 down to 0.38 and 0.40. Having two spatial links at different heights is essential to overcome body shadowing.
Second: Motion energy and Doppler bandpowers are the primary predictive drivers; stripping them causes the largest performance drops.
Third: Static features alone collapse to 0.353 F1, proving once again that static multipath cannot recognize dynamic human kinematics."""
        ),

        # Slide 22: Live Engine Architecture
        ("Live Real-Time Streaming Engine Architecture (app/engine_proc.py)", "Live System Engineering", "Speaker 4",
         [("Decoupled Multi-Process Architecture (D-057)", "Overcoming Streamlit GIL Contention", [
             "The Problem: In initial testing, running Streamlit web GUI and CSI serial ingestion in a single process caused GIL lock contention, degrading engine step rate from 0.50 s to 1.45 s (p90 2.27 s).",
             "The Fix (D-057): Separated into a decoupled two-process architecture:",
             "  1. Engine Daemon (app/engine_proc.py): Native background process reading serial streams, maintaining circular ring buffers, and executing inference every 500 ms.",
             "  2. GUI Dashboard (app/live_app.py): Streamlit web interface polling predictions via local authenticated IPC socket.",
             "Outcome: Live step compute locked at 383 ms median, stepping precisely every 0.50 s."
         ]),
          ("Safety Features & Zero Stale Window Protection (D-053)", "Defensive Live Runtime", [
             "Stale Buffer Detection: If any receiver falls silent for > 1.0 s, engine outputs 'degraded' or 'no_signal', NEVER predicting on stale packets.",
             "Auto-Reconnection: Recovers dynamically via /dev/serial/by-id hardware tokens on unplug/replug.",
             "BLAS Single-Threading: Limited OpenBLAS to 1 thread on host laptop, slashing step compute from 533 ms to 251 ms."
         ])],
         """Speaker 4: I am Speaker 4, and I will present our live deployment, hardware troubleshooting, and conclusions.
In Phase 5, we deployed our real-time streaming engine. In our first test, the system lagged terribly, with step intervals ballooning to 1.45 seconds! We diagnosed the issue: Streamlit's web browser rendering was fighting our signal processing code for Python's Global Interpreter Lock.
Under Decision D-057, we refactored the engine into a separate, dedicated native process communicating with the dashboard over a local IPC socket. This locked our live inference cycle to exactly 500 milliseconds. We also added safety guards that immediately flag degraded signal if a sensor unplugs, preventing stale predictions."""
        ),

        # Slide 23: Live Test & RX2 Diagnostic
        ("Live Library Field Trials & The RX2 Connector Diagnostic", "Live Hardware Debugging", "Speaker 4",
         [("The Morning Live Mystery (Session 3)", "Complete Loss of Motion Response", [
             "The Symptom: Live test ran for 14 min without crashing, but walking across the link was called 'empty' (walk 3/83) and the fall produced zero alarm (max P = 0.33).",
             "Offline Verification: Diagnostic takes recorded on the boards failed identically offline, proving the software was innocent—the issue was physical RF!",
             "The Anomaly: RX2 RSSI was 4.5 dB abnormally high (-33.6 dBm vs -38 dBm baseline), yet RX2 motion features sat at the 0th to 5th percentile (completely motion-blind!)."
         ]),
          ("The Antenna Swap Test & U.FL Resolution (D-060)", "Systematic Hardware Isolation", [
             "Antenna Swap (Round 3): Swapped Antenna A (from RX1) to RX2, and Antenna B to RX1.",
             "The Discovery: RX2 immediately sprang to life! Motion features surged to the 72nd–97th percentile. Walking was recognized 47/52 times. RX1 remained healthy with Antenna B.",
             "Root Cause Identified: A poorly mated U.FL micro-coaxial connector on RX2. It created RF reflection and severe static leakage that blinded the receiver to dynamic Doppler shifts.",
             "Resolution: Firmly reseated the U.FL connector and confirmed vertical polarization, restoring normal sensing."
         ])],
         """Speaker 4: Slide 23 presents an extraordinary real-world engineering investigation from our morning session in the library.
When we powered up the system, walking across the room was called 'empty' and the fall triggered zero alarm! We verified our code—it was flawless. We then inspected the hardware signals and noticed that Receiver 2 had an RSSI 4.5 dB too high, yet its motion features were stuck at the zero-th percentile—it was completely motion-blind!
To isolate the fault, we executed a systematic antenna swap test. Instantly, Receiver 2 recovered, recognizing walks 47 out of 52 times. The root cause was an unseated U.FL micro-connector on the circuit board. Reseating it firmly restored full sensitivity."""
        ),

        # Slide 24: Final Live 14-Minute Continuous Run
        ("Final 14-Minute Continuous Live Field Validation Results", "Live System Validation", "Speaker 4",
         [("Continuous Live Run Overview (2026-10-23 11:40–11:53)", "1658 Steps at 0.50 s Interval", [
             "Physical Setup: College Library Reading Hall, campus Wi-Fi active, spoken audio cues.",
             "System Health: Ran continuously for 14 minutes (1658 inference cycles) with zero crashes.",
             "Walk Across Link (Path 2, Horizontal): 37 of 42 windows correctly identified as Walk (88.1% recall)! Triggered 2 false fall alarms during fast walking (P = 0.57, 0.50).",
             "Walk Along Link (Path 1, Vertical): 6 of 51 windows correct (mostly called 'empty'; reveals Doppler blind zone).",
             "Simulated Mattress Fall: Event detected in 2 windows, but max P(fall) = 0.28 (failed to cross θ = 0.50 threshold -> NO ALARM)."
         ]),
          ("Analytical Assessment of Live Reality", "Why Live Diverged from LOSO", [
             "1. Presence Fragility: Logistic regression presence boundary sits inside empty-room variance; empty room was called occupied in 17/52 windows, corrupting state transitions.",
             "2. Doppler Geometric Blind Spot: Moving along the line of sight (Path 1) produces minimal path-length changes, blinding the single-axis link.",
             "3. RF Co-Channel Traffic: Campus library APs operating on Channel 11 caused burst packet loss up to 8%."
         ])],
         """Speaker 4: Following the connector repair, we conducted our final 14-minute continuous live trial in the library hall across 1658 consecutive inference cycles.
The results demonstrated both triumphs and real-world limits:
When walking across the link on Path 2, the system recognized walking in 37 out of 42 windows—an 88% success rate, alongside 2 false alarms during fast walking.
However, walking along the link on Path 1 was mostly missed, revealing a geometric Doppler blind zone.
Furthermore, while the fall was detected in 2 windows, its probability peaked at 0.28, failing to cross the 0.50 threshold to sound the alarm. Ambient library Wi-Fi interference and presence baseline drift reduced live sensitivity relative to offline benchmarks."""
        ),

        # Slide 25: Limitations
        ("Systemic Limitations & Open Engineering Challenges", "Limitations & Integrity", "Speaker 4",
         [("Scope Limitations (Mandatory Compliance)", "Boundary Conditions of Study", [
             "1. Confined Physical Domain: All experimental data gathered in a single room (library hall) with fixed furniture.",
             "2. Demographic Homogeneity: 6 healthy university volunteers (young adults); gait kinematics and body mass do not reflect frail geriatric demographics.",
             "3. Simulated Fall Constraints: Falls performed onto a high-density mattress at a single spot (Spot M); cannot prove fall detection elsewhere in the room.",
             "4. Ground Truth Proxies: No multi-camera optical motion-capture ground truth; timing relies on audio countdowns and DSP energy onset proxies.",
             "5. Non-Clinical Device: Prototype is an academic proof-of-concept, not a certified life-safety device."
         ]),
          ("Core Technical Deficiencies", "Engineering Bottlenecks", [
             "Presence Baseline Drift: Static profile shifts cause the presence classifier to misidentify empty rooms as occupied.",
             "Directional Blind Zones: Single-axis LoS links struggle to detect motion parallel to the radio beam.",
             "Hardware RF Vulnerability: U.FL connector mating can silently blind Doppler sensitivity without triggering an RSSI drop."
         ])],
         """Speaker 4: In keeping with our commitment to engineering integrity, Slide 25 outlines the explicit boundaries of our study.
First: Our dataset comes from a single library room, one geometry, and 6 healthy young volunteers performing simulated falls onto a mattress at Spot M. It is not clinically validated.
Second: We discovered real technical bottlenecks: directional blind zones along the radio link, presence baseline drift across different days, and the physical vulnerability of micro-RF connectors.
Acknowledging these limitations openly is essential for credible engineering research."""
        ),

        # Slide 26: Conclusion & Viva
        ("Academic Conclusion, Future Roadmap & Viva Voce Defense", "Conclusion & Defense", "Speaker 4",
         [("Key Project Achievements", "Summary of Deliverables", [
             "• Built End-to-End Testbed: Low-cost COTS ESP32-S3 transceivers capturing 114 subcarriers at 200 Hz.",
             "• Rigorous DSP Pipeline: Created anti-aliased, gain-normalized, phase-sanitized feature space f2.",
             "• Unbiased Evaluation: Proved classical models beat deep learning on small CSI data (F1: 0.70 presence, 0.57 state, 0.54 events; 21/42 falls caught).",
             "• 100% Reproducible: Automated script rebuilds features, retrains models, and validates 801 raw file checksums in 11 minutes (Phase 6 Certified)."
         ]),
          ("Future Technical Roadmap", "Next-Generation Enhancements", [
             "1. Guided Site Calibration: 60-second automated empty-room baseline capture on startup (docs/analysis/calibration_proposal.md).",
             "2. Multi-Angle Spatial Diversity: Add a 3rd receiver at 90° azimuth to eliminate geometric Doppler blind spots.",
             "3. Automated Hardware Health Check: Implement preflight loopback tests to detect unseated RF connectors.",
             "Thank you! We now welcome questions from the examination committee."
         ])],
         """Speaker 4: In conclusion, we have designed, implemented, and validated a complete device-free human activity recognition and fall detection platform. We proved that classical machine learning with physics-grounded features outperforms complex deep neural networks on small CSI datasets, while maintaining 100% privacy at $15 hardware cost.
Our entire codebase is fully reproducible in 11 minutes from raw bytes.
We thank our guide, Dr. Leena Chandrashekar, reviewer Dr. Srikanth G N, and the Department of ECE. We are now open for viva voce questions."""
        )
    ]

    # Iterate and build slides 3 to 26
    for idx, (title, category, speaker, cards, notes) in enumerate(slides_data, start=3):
        s = prs.slides.add_slide(blank_layout)
        add_header(s, title, category, speaker)

        if len(cards) == 2:
            left_widths = [5.7, 5.7]
            left_pos = [0.8, 6.8]
            for c_idx, (c_title, c_subtitle, bullets) in enumerate(cards):
                c = add_card(s, left_pos[c_idx], 1.4, left_widths[c_idx], 5.6, c_title)
                tb = s.shapes.add_textbox(Inches(left_pos[c_idx] + 0.2), Inches(2.0), Inches(left_widths[c_idx] - 0.4), Inches(4.7))
                tf = tb.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = c_subtitle
                p.font.bold = True
                p.font.size = Pt(12)
                p.font.color.rgb = C_PRIMARY if c_idx == 1 else C_SECONDARY

                for b in bullets:
                    bp = tf.add_paragraph()
                    bp.text = f"• {b}"
                    bp.font.size = Pt(10.5)
                    bp.font.color.rgb = C_TEXT_DARK
        elif len(cards) == 1:
            c_title, c_subtitle, bullets = cards[0]
            c = add_card(s, 0.8, 1.4, 11.7, 5.6, c_title)
            tb = s.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(11.3), Inches(4.7))
            tf = tb.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = c_subtitle
            p.font.bold = True
            p.font.size = Pt(13)
            p.font.color.rgb = C_PRIMARY

            for b in bullets:
                bp = tf.add_paragraph()
                bp.text = f"• {b}"
                bp.font.size = Pt(11)
                bp.font.color.rgb = C_TEXT_DARK

        set_speaker_notes(s, notes)

    out_path = "WiFi_CSI_HAR_26_Slides_Final.pptx"
    prs.save(out_path)
    print(f"Presentation saved successfully to {out_path} ({len(prs.slides)} slides).")

if __name__ == "__main__":
    build_presentation()
