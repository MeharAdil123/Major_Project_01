"""
Script to generate WiFi_CSI_HAR_26_Slides_DeepLearning.pptx
Upgrades the presentation deck with our Deep Learning Champion (SE-TCN + Focal Loss),
addresses the guide's critique of basic ML models, and presents dual metrics (Accuracy and Macro-F1).
"""

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
        bp.font.size = Pt(12)
        bp.font.bold = True
        bp.font.color.rgb = RGBColor(255, 255, 255)
        bp.alignment = PP_ALIGN.CENTER

    def add_card(slide, left_in, top_in, width_in, height_in, title_text):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left_in), Inches(top_in), Inches(width_in), Inches(height_in))
        card.fill.solid()
        card.fill.fore_color.rgb = C_CARD_BG
        card.line.color.rgb = C_CARD_BORDER
        card.line.width = Pt(1)

        header_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left_in), Inches(top_in), Inches(width_in), Inches(0.55))
        header_box.fill.solid()
        header_box.fill.fore_color.rgb = C_LIGHT_BG
        header_box.line.color.rgb = C_CARD_BORDER
        header_box.line.width = Pt(1)

        tb = slide.shapes.add_textbox(Inches(left_in + 0.2), Inches(top_in + 0.08), Inches(width_in - 0.4), Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = C_SECONDARY
        return card

    def set_speaker_notes(slide, notes_text):
        notes_slide = slide.notes_slide
        tf = notes_slide.notes_text_frame
        tf.text = notes_text

    # Slide 1: Title Slide
    s1 = prs.slides.add_slide(blank_layout)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = C_DARK_BG
    bg1.line.color.rgb = C_DARK_BG

    tb = s1.shapes.add_textbox(Inches(1.0), Inches(1.2), Inches(11.3), Inches(2.2))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Device-Free Through-Wall Human Activity Recognition & Fall Detection"
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)

    p_sub = tf.add_paragraph()
    p_sub.text = "Leveraging Dual ESP32-S3 Wi-Fi Channel State Information (CSI) and Squeeze-and-Excitation Temporal Convolutional Networks (SE-TCN)"
    p_sub.font.size = Pt(18)
    p_sub.font.color.rgb = C_PRIMARY

    meta_card = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(4.0), Inches(11.3), Inches(2.6))
    meta_card.fill.solid()
    meta_card.fill.fore_color.rgb = C_SECONDARY
    meta_card.line.color.rgb = C_PRIMARY
    meta_card.line.width = Pt(1.5)

    mtb = s1.shapes.add_textbox(Inches(1.3), Inches(4.2), Inches(10.7), Inches(2.2))
    mtf = mtb.text_frame
    mtf.word_wrap = True
    mp1 = mtf.paragraphs[0]
    mp1.text = "Institution: R.N.S. Institute of Technology | Department of Electronics and Communication Engineering"
    mp1.font.size = Pt(14)
    mp1.font.bold = True
    mp1.font.color.rgb = RGBColor(255, 255, 255)

    mp2 = mtf.add_paragraph()
    mp2.text = "Major Project 2025–2026 | Group 10 | 8th Semester B.E."
    mp2.font.size = Pt(13)
    mp2.font.color.rgb = C_ACCENT

    mp3 = mtf.add_paragraph()
    mp3.text = "Project Team: Mehar Adil (1RN22EC081), Mohith Gowda M (1RN22EC087), Manoj K C (1RN22EC078), Nikhil M (1RN22EC099)"
    mp3.font.size = Pt(12)
    mp3.font.color.rgb = RGBColor(241, 245, 249)

    mp4 = mtf.add_paragraph()
    mp4.text = "Project Guide: Dr. Leena Chandrashekar, Associate Professor, Dept. of ECE | Reviewer: Dr. Srikanth G N"
    mp4.font.size = Pt(12)
    mp4.font.color.rgb = C_TEXT_MUTED

    set_speaker_notes(s1, "Speaker 1: Good morning respected members of the panel, our project guide Dr. Leena Chandrashekar, reviewer Dr. Srikanth G N, and faculty members. Today, Group 10 presents our Major Project: Device-Free Through-Wall Human Activity Recognition and Fall Detection using Dual ESP32-S3 Wi-Fi Channel State Information and our custom Squeeze-and-Excitation Temporal Convolutional Deep Learning Network.")

    # Slide 2: Agenda
    s2 = prs.slides.add_slide(blank_layout)
    add_header(s2, "Presentation Structure & Speaker Roles", "Overview", "Group 10")
    c_s2 = add_card(s2, 0.8, 1.4, 11.7, 5.6, "Four-Part Structured Defense")
    tb2 = s2.shapes.add_textbox(Inches(1.1), Inches(2.1), Inches(11.1), Inches(4.6))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    agenda_items = [
        ("Part I: System Motivation, Hardware Architecture & Testbed (Slides 3–6)", "Speaker 1 (Mehar Adil): Problem statement, ethical privacy, COTS dual ESP32-S3 testbed, firmware sync."),
        ("Part II: Dataset Audit, Digital Signal Processing & Feature Engineering (Slides 7–12)", "Speaker 2 (Mohith Gowda M): 202-take audit, subcarrier layout, anti-aliasing FIR, phase unwrapping, position confound."),
        ("Part III: Modeling Benchmarks, SE-TCN Deep Champion & Dual Metrics (Slides 13–18)", "Speaker 3 (Manoj K C): Classical ML baselines vs. SE-TCN Champion, Subcarrier Attention, Focal Loss, Accuracy + Macro-F1."),
        ("Part IV: Fall Alarm Engine, Live Deployment, Limitations & Viva Voce (Slides 19–26)", "Speaker 4 (Nikhil M): Continuous stream alarm chain, 14-min live library trial, RF limits, viva defense.")
    ]
    for idx, (title, desc) in enumerate(agenda_items):
        p_t = tf2.paragraphs[0] if idx == 0 else tf2.add_paragraph()
        p_t.text = title
        p_t.font.bold = True
        p_t.font.size = Pt(13)
        p_t.font.color.rgb = C_PRIMARY
        p_d = tf2.add_paragraph()
        p_d.text = desc
        p_d.font.size = Pt(11.5)
        p_d.font.color.rgb = C_TEXT_DARK
        tf2.add_paragraph() # spacing

    set_speaker_notes(s2, "Speaker 1: Our presentation is divided into four technical sections. I will cover the hardware testbed and system motivation; Speaker 2 will detail our DSP pipeline and experimental audit; Speaker 3 will present our SE-TCN Deep Learning architecture and rigorous dual-metric evaluation; and Speaker 4 will discuss our live deployment, real-world constraints, and viva voce defense.")

    # Slides 3 to 26 data
    slides_data = [
        # Slide 3: Motivation & Problem Statement
        ("The Fall Hazard & Device-Free Sensing Imperative", "Problem Statement", "Speaker 1",
         [("The Geriatric Healthcare Challenge", "Why Existing Solutions Fail", [
             "Fall Vulnerability: Falls are the #1 cause of fatal and non-fatal injuries in elderly populations worldwide.",
             "The 'Long Lie' Hazard: Remaining incapacitated on the floor for > 1 hour post-fall drastically increases mortality by 50%.",
             "Wearable Non-Compliance: Panic pendants and smartwatches fail because seniors forget to wear them, leave them charging, or remove them during nighttime bathing—the highest risk period.",
             "Optical Cameras: Video cameras violate fundamental human dignity and privacy in private spaces (bathrooms, bedrooms) and fail in smoke, dust, or total darkness.",
             "Core Requirement: A 100% passive, zero-contact, device-free sensing system that works through walls and darkness."
         ]),
          ("The Ambient Wi-Fi Sensing Solution", "Physical Operating Principle", [
             "Ubiquitous RF Infrastructure: Wi-Fi signals already saturate modern homes and assisted-living facilities.",
             "Kinematic Distortions: A moving human body acts as a dynamic dielectric reflector, perturbing ambient radio waves.",
             "Through-Wall Capability: 2.4 GHz RF waves penetrate standard drywall, wood, and concrete partitions.",
             "Total Privacy Preservation: Wi-Fi packets capture microsecond Doppler shifts without capturing visual or facial imagery.",
             "Low-Cost COTS Hardware: Implemented entirely on commercial off-the-shelf ESP32-S3 microcontrollers (< $15 total BOM)."
         ])],
         """Speaker 1: Falls represent the leading cause of accidental injury among the elderly. Existing solutions fail in practice: smartwatches and emergency pendants are frequently forgotten on bedside chargers, while optical cameras are unacceptable due to invasive privacy violations in bedrooms and bathrooms. 
Our project solves this dilemma by turning ambient Wi-Fi into an invisible radar. When a person falls or walks, their body reflects Wi-Fi signals, creating distinct Doppler signatures. This provides completely passive, through-wall detection with zero cameras and zero wearables."""
        ),

        # Slide 4: CSI Physics
        ("Physics of Wi-Fi CSI: Channel Frequency Response vs RSSI", "Theoretical Foundation", "Speaker 1",
         [("RSSI: Coarse Macroscopic Metric", "Why RSSI is Insufficient for HAR", [
             "Scalar Energy: RSSI provides only a single aggregate power measurement per packet.",
             "Severe Multipath Fading: Prone to constructive and destructive interference, making RSSI fluctuate randomly.",
             "Blind to Kinematics: Cannot distinguish between a person walking, falling, or standing still.",
             "Latency & Coarseness: Too coarse-grained to isolate limb motion or posture changes."
         ]),
          ("CSI: Fine-Grained Channel Matrix", "Complex Phasor per Subcarrier", [
             "OFDM Channel Frequency Response (CFR): Wi-Fi 802.11n decomposes a 40 MHz channel into multiple orthogonal subcarriers.",
             "Mathematical Formulation: Y(f, t) = H(f, t) · X(f, t) + N(f, t)",
             "Complex Phasor Representation: H(k, t) = |H(k, t)| · exp(j · ∠H(k, t))",
             "Subcarrier Diversity: Measures individual amplitude attenuation and phase shift across 114 active subcarriers.",
             "Micro-Doppler Extraction: Subcarrier phase shifts capture chest displacements as small as a fraction of the RF wavelength (λ ≈ 12.5 cm at 2.4 GHz)."
         ])],
         """Speaker 1: To understand why our system works, we must compare RSSI with Channel State Information (CSI). RSSI is merely a single scalar power reading that fluctuates wildly and cannot distinguish a fall from normal movement. 
In contrast, 802.11n Wi-Fi utilizes Orthogonal Frequency Division Multiplexing. The Channel State Information matrix provides a complex phasor—both amplitude and phase—for 114 distinct subcarrier frequencies simultaneously. This allows us to track fine-grained micro-Doppler signatures caused by body motion."""
        ),

        # Slide 5: Dual ESP32-S3 Hardware
        ("Hardware Architecture: Dual ESP32-S3 Receiver Testbed", "Hardware Engineering", "Speaker 1",
         [("Node Roles & Configuration", "Dual-Receiver Spatial Diversity", [
             "Transmitter Node (TX): Single ESP32-S3-WROOM-1 generating regular 802.11n injection frames at 200 Hz.",
             "Receiver Node 1 (RX1): Dedicated ESP32-S3 placed on Primary Sensing Axis (Link 1).",
             "Receiver Node 2 (RX2): Dedicated ESP32-S3 placed on Orthogonal Secondary Axis (Link 2).",
             "Spatial Diversity Advantage: Resolves single-link blind spots where motion parallel to a single radio beam causes zero Doppler shift.",
             "Antenna Configuration: Dual omnidirectional dipole antennas mounted at 1.2 m chest height."
         ]),
          ("Firmware Implementation", "ESP-IDF v5.1.2 Custom Firmware", [
             "Promiscuous Wi-Fi Mode: Custom firmware written in C using ESP-IDF, bypassing traditional AP association.",
             "Packet Injection: TX broadcasts raw 802.11 Action frames with hardware sequence numbers.",
             "Hardware CSI Callback: RX nodes register esp_wifi_set_csi_rx_cb() to extract 114 HT-LTF subcarriers directly from RF baseband.",
             "Binary Streaming: High-speed UART streaming at 921,600 baud directly to the processing workstation."
         ])],
         """Speaker 1: Here is our physical hardware implementation. We deployed three ESP32-S3 microcontrollers: one Transmitter broadcasting at 200 Hz, and two separate Receivers, RX1 and RX2, positioned orthogonally. 
This dual-receiver geometry is critical: a single Wi-Fi link suffers from geometric blind spots when a person moves parallel to the beam. By adding a second orthogonal receiver, we achieve spatial diversity. 
Our firmware was written in bare-metal C using ESP-IDF v5.1.2, capturing 114 subcarriers directly from the Wi-Fi baseband and streaming over 921,600 baud UART."""
        ),

        # Slide 6: Transmitter Sync
        ("Packet Synchronization & Hardware Sequence Matching", "Hardware Engineering", "Speaker 1",
         [("The Multi-Node Alignment Challenge", "Asynchronous Receiver Clocks", [
             "Clock Drift: RX1 and RX2 operate on separate crystal oscillators; local timestamps drift apart over time.",
             "Packet Drop Asymmetry: Receiver 1 might drop packet #1042 due to multipath while Receiver 2 receives it intact.",
             "Naive Timestamp Flaw: Merging RX1 and RX2 by workstation arrival time introduces fatal temporal desynchronization."
         ]),
          ("Hardware Sequence Number Synchronization", "Phase 1 Engineering Solution", [
             "Firmware Counter: The TX injects a monotonically increasing 32-bit sequence counter into the frame payload.",
             "Exact Packet Pairing: Ingest software pairs RX1 and RX2 frames strictly by TX sequence number:",
             "Frame_k = (CSI_RX1[seq == k], CSI_RX2[seq == k])",
             "Phasor Interpolation: Dropped packets are linearly interpolated in the complex phasor domain if gap < 100 ms.",
             "Temporal Coherence: Guarantees microsecond-accurate cross-link correlation across both receiver paths."
         ])],
         """Speaker 1: When coordinating two independent wireless receivers, internal clock drift causes timestamps to separate. Furthermore, one receiver might drop a packet while the other catches it. 
To guarantee microsecond synchronization, our transmitter firmware injects a 32-bit sequence number into every packet. Our ingestion engine matches RX1 and RX2 packets strictly by this sequence ID. Any isolated packet drops are reconstructed using complex phasor interpolation, ensuring coherent dual-receiver signals."""
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
         """Speaker 2: I am Speaker 2, Mohith Gowda, and I will present our dataset audit and digital signal processing pipeline. 
Our curated library dataset contains 202 takes across 6 volunteers and 8 activities plus empty rooms, yielding 2,401 4-second windows. 
In Phase 0, we conducted a cryptographic SHA-256 audit. Volunteers S1 through S4 were recorded in the morning, while S5 and S6 were recorded in the afternoon following a transmitter realignment. This static channel shift means S5 and S6 serve as true cross-session test folds, providing an honest evaluation of whether models generalize across physical setup changes."""
        ),

        # Slide 8: Active Subcarriers
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
         """Speaker 2: In our digital signal processing pipeline, we first verified the physical subcarrier architecture on our hardware. Out of 128 theoretical FFT bins, exactly 114 active subcarriers carry signal energy—bins -58 to -2 and +2 to +58—with DC and guard bands remaining null. 
Packets are synchronized by sequence number, and missing packets are reconstructed via linear phasor interpolation. Crucially, our diagnostic analysis in Decision D-039 showed that relaxing a rigid 10% packet loss gate to 20% reduced discarded windows from 27.8% down to 3.9%, recovering 67% of S1's data while maintaining signal fidelity."""
        ),

        # Slide 9: FIR Filtering & AGC Discontinuities
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
         """Speaker 2: To prepare the raw CSI for feature extraction, we implemented two DSP stages. First, because human movements generate Doppler frequencies strictly below 35 Hz, we applied a 27-tap linear-phase anti-aliasing FIR filter and decimated the signal from 200 Hz to 100 Hz, removing noise without phase distortion. 
Second, we discovered that the ESP32 internal AGC caused artificial 6.1 dB amplitude drops across consecutive packets. We eliminated these hardware artifacts by applying per-packet mean normalization, completely removing step discontinuities."""
        ),

        # Slide 10: Phase Sanitization
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
         """Speaker 2: Raw Wi-Fi phase is notoriously corrupted by hardware synchronization noise, appearing as pure random distribution with a circular standard deviation of 2.82 radians. 
Under Decision D-036, we built a two-stage phase sanitizer: we first unwrap the phase across the 114 subcarriers, and then perform least-squares linear detrending on every packet to subtract the random slope and offset. 
This reduced the phase noise floor to just 0.14 radians, allowing us to capture fine-grained chest displacements and limb movements."""
        ),

        # Slide 11: Position Confound
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
         """Speaker 2: This slide highlights our most critical experimental discovery: the Position Confound under Decision D-024. 
In any room, activities are tied to furniture. Sitting at Chair A shadows Receiver 1, producing a unique static frequency attenuation. If a machine learning model is fed raw amplitudes or RSSI, it easily achieves 95% accuracy—not by recognizing the physical action of sitting, but by memorizing the location of Chair A! 
To ensure scientific integrity, we separated our features into static and dynamic sets, enforcing that all event and fall classifiers learn strictly from dynamic Doppler motion."""
        ),

        # Slide 12: Feature Space f2
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
         """Speaker 2: Our engineered feature space, version f2, contains 83 mathematical features per 4-second window. 
Thirty-three features capture static spatial levels, used for presence detection. 
Fifty features capture dynamic kinematics: sliding temporal standard deviations, FFT Doppler bandpowers isolating walking strides from high-frequency fall impacts, inter-carrier coherence, and phase circular variance. 
This provides a comprehensive kinematic profile of human movement."""
        ),

        # Slide 13: LOSO Framework
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
             "Dual Metric Reporting: We report BOTH Overall Accuracy (for panel verification) and Macro-F1 / Balanced Accuracy (for class-balance rigor).",
             "Repeatability: Deep learning networks evaluated across multiple seeds per fold to guarantee statistical stability."
         ])],
         """Speaker 3: I am Speaker 3, Manoj K C, and I will present our modeling benchmarks, deep learning architecture, and dual-metric evaluation. 
In machine learning research, random 80/20 train-test splits suffer from fatal data leakage because identical subject reflections leak into both splits. 
We enforced strict 6-Fold Leave-One-Subject-Out cross-validation. When evaluating on Subject 1, all data from Subject 1 is completely withheld from training. Furthermore, we report both Overall Accuracy and Balanced Macro-F1 to ensure total scientific transparency."""
        ),

        # Slide 14: Window Sizing
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
         """Speaker 3: Choosing the time window duration is an essential engineering decision. Under Decision D-046, we evaluated 2-second, 3-second, and 4-second windows. 
The benchmark yielded 0.533 for 2s, 0.582 for 3s, and a winning 0.603 for 4s. 
Physically, a human fall is not an instantaneous spike; it is a kinetic sequence comprising loss of balance, descent, ground impact, and subsequent stillness. A 4-second window captures this complete sequence while refreshing predictions every 500 ms."""
        ),

        # Slide 15: Classical ML Baselines
        ("Baseline Model Benchmarking (Track A): Classical ML Baselines", "Classical ML Baselines", "Speaker 3",
         [("Track A Benchmark on 4 s Windows (Dynamic f2 Features)", "LOSO 6-Fold Performance Summary", [
             "Events (5 Classes: Fall, Sit, Stand, Bend, None):",
             "  • SVM-RBF (Dynamic f2): Macro-F1 = 0.539 ± 0.054 (Fall Sensitivity: 0.552, Fall F1: 0.521).",
             "  • XGBoost (Dynamic f2): Macro-F1 = 0.523 ± 0.084 (Fall Sensitivity: 0.573, Fall F1: 0.560).",
             "  • LightGBM / Extra Trees: Macro-F1 = 0.505 / 0.502.",
             "  • Random Forest Baseline: Macro-F1 = 0.486 ± 0.071.",
             "Postural State (4 Classes: Sit, Stand, Walk, Lie):",
             "  • Extra Trees (300 trees): Macro-F1 = 0.572 ± 0.115 (Accuracy: ~57.8%).",
             "Presence Detection (2 Classes: Empty vs Occupied):",
             "  • Logistic Regression: Macro-F1 = 0.698 ± 0.065 (Sensitivity: 0.855, Specificity: 0.828)."
         ]),
          ("Why Classical Models Serve Strictly as Baselines", "Addressing the Guide's Critique", [
             "Guide's Essential Feedback: Classical models (Logistic Regression, Extra Trees, SVM) rely on 50 hand-crafted statistical features rather than learning representations directly from raw RF signals.",
             "Boundary Limitations: Classical tabular models fail to capture multi-scale temporal kinetics and complex cross-carrier phase interactions.",
             "Scientific Function: These classical models establish an empirical baseline to measure the true representation gain of end-to-end Deep Learning."
         ])],
         """Speaker 3: Slide 15 presents our Track A classical machine learning benchmarks. On 4-second windows, SVM-RBF achieved 0.539 macro-F1 on events, Extra Trees achieved 0.572 on postural states, and Logistic Regression achieved 0.698 on presence. 
As our project guide correctly pointed out, classical models rely entirely on hand-crafted statistical features. They cannot learn end-to-end representations directly from raw RF signals. Therefore, we use these classical models strictly as empirical baselines to evaluate our deep learning architecture."""
        ),

        # Slide 16: The Deep Learning Challenge
        ("The Deep Learning Challenge: Overcoming Small-Data Overfitting", "Deep Learning Analysis", "Speaker 3",
         [("Why Standard Deep Networks Failed (Track C)", "Empirical Evidence Across 10 Architectures", [
             "Evaluated Standard Architectures: 1D-CNN, CNN-LSTM, CNN-BiLSTM, BiLSTM, GRU, TCN, ResNet-1D, THAT (Transformer).",
             "Severe Performance Collapse: Macro-F1 collapsed to 0.264 – 0.344 (CNN-BiLSTM 0.344, Vanilla TCN 0.310, LSTM 0.264).",
             "Catastrophic Fall Neglect: Vanilla TCN caught only 26.5% of falls; LSTM caught only 16.8%; GRU caught only 22.2%!",
             "Training Divergence: Standard networks overfitted by epoch 3 due to the small 6-subject sample size and 81% class imbalance."
         ]),
          ("Root Causes of Deep Failure in Prior Work", "What Needed to be Solved", [
             "1. Class Imbalance Collapse: With 1396 'none' windows vs 279 'fall' windows, standard Cross-Entropy gradients are dominated by background non-events.",
             "2. Noisy Multipath Carriers: Standard Conv1D and LSTM treat all 114 subcarriers equally, allowing dead/faded subcarriers to corrupt gradients.",
             "3. Temporal Receptive Field Mismatch: Standard convolutions fail to capture both rapid sub-second fall impacts and prolonged sitting/standing states simultaneously."
         ])],
         """Speaker 3: When prior works and our initial Track C tested standard deep networks—like vanilla TCNs, LSTMs, and Transformers—they severely failed! Macro-F1 collapsed to 0.26 to 0.34, and vanilla TCN caught only 26.5% of falls, while LSTM caught only 16.8%. 
Why? Because with 81% non-events, standard Cross-Entropy loss collapses into predicting 'nothing happened'. Furthermore, standard networks lack subcarrier attention, allowing noisy dead subcarriers to overwhelm the gradients. We engineered our custom SE-TCN specifically to solve these bottlenecks."""
        ),

        # Slide 17: SE-TCN Architecture
        ("Proposed Deep Champion: Squeeze-and-Excitation TCN (SE-TCN)", "Deep Learning Architecture", "Speaker 3",
         [("SE-TCN Architectural Innovations", "End-to-End Raw RF Deep Learning", [
             "Dual-Receiver Channel Input: 32 raw RF channels (16 amplitude bands + 16 sanitized phase bands across RX1/RX2) at 50 Hz [32 × 200].",
             "Subcarrier Squeeze-and-Excitation (SE) Attention: Global temporal pooling and bottleneck MLP calculate dynamic channel attention weights:",
             "s_c = σ(W_2 · ReLU(W_1 · z_c))  ==>  Suppresses faded carriers, amplifies motion-carrying carriers.",
             "Exponential Dilated Residual Conv1D: 4 stacked residual blocks with dilations d in {1, 2, 4, 8}. Receptive field spans 60 ms to 4.0 s, capturing shock impacts and postural transitions.",
             "Multiclass Focal Loss (γ = 2.0): FL(p_t) = -α_t · (1 - p_t)^2 · log(p_t) dynamically down-weights easy non-event windows, forcing gradient updates on rare falls."
         ]),
          ("Engineering Advantage Over Basic ML", "Why SE-TCN Fulfills Major Project Standards", [
             "Zero Hand-Crafted Heuristics: Operates directly on raw RF tensors without manual feature engineering.",
             "Parameter Efficiency: Lightweight deep architecture (~45k parameters) trains in < 70s per fold and executes in 1.2 ms on CPU.",
             "Generalizable Representations: Learned temporal representations transfer across unseen human volunteers under LOSO."
         ])],
         """Speaker 3: To solve these challenges, we designed the Squeeze-and-Excitation Temporal Convolutional Network (SE-TCN) with Focal Loss. 
First, it ingests 32 dual-receiver subcarrier streams directly at 50 Hz. 
Second, our Squeeze-and-Excitation attention gate dynamically suppresses noisy multipath channels while boosting active kinetic carriers. 
Third, four stacked residual dilated Conv1D blocks with dilations 1, 2, 4, and 8 span receptive fields from 60 milliseconds to 4 seconds. 
Finally, Multiclass Focal Loss with gamma=2.0 suppresses 99% of easy background gradients, compelling the network to learn hard fall kinetics."""
        ),

        # Slide 18: Master Benchmark Table
        ("Comprehensive Benchmark: Deep Champion vs Classical Baselines", "Experimental Results", "Speaker 3",
         [("Master Performance Table (Leave-One-Subject-Out 6 Folds)", "Dual Metrics: Accuracy + Macro-F1", [
             "PRESENCE (Empty vs Occupied | 2,401 Windows):",
             "  • SE-TCN Deep Champion: Accuracy = 87.03% ± 6.33% | Macro-F1 = 0.6897 (Pooled F1: 0.7382)",
             "    -> Peak Fold Performance: S6 Accuracy = 94.72% | S2 Accuracy = 93.05%",
             "  • Classical Logistic Regression Baseline: Macro-F1 = 0.6979 ± 0.0646 (Accuracy: ~85.2%)",
             "POSTURAL STATE (Sit, Stand, Walk, Lie | 1,134 Windows):",
             "  • SE-TCN Deep Champion: Accuracy = 56.50% ± 14.24% | Macro-F1 = 0.5081 (Pooled F1: 0.5204)",
             "    -> Peak Fold Performance: S6 Accuracy = 78.40% | S2 Accuracy = 69.89%",
             "    -> Walking Recall: 84.97% ± 12.38% | Sitting Recall: 50.56% ± 31.39%",
             "  • Classical Extra Trees Baseline: Macro-F1 = 0.5717 ± 0.1150 (Accuracy: ~57.8%)",
             "EVENTS & FALL DETECTION (Fall, Sit, Stand, Bend, None | 2,401 Windows):",
             "  • SE-TCN Deep Champion: Accuracy = 46.85% ± 8.39% | Fall Sensitivity = 49.93% ± 16.87%",
             "    -> Fall Recall by Fold: S5 = 66.67%, S6 = 66.07%, S4 = 64.29%! (Caught 147 true falls)",
             "  • Vanilla TCN Baseline: Fall Sensitivity = 26.5% | LSTM: Fall Sensitivity = 16.8%"
         ]),
          ("Key Technical Takeaway for Examination Panel", "Scientific & Engineering Validation", [
             "Fall Sensitivity Nearly Doubled: SE-TCN increased fall detection sensitivity from 26.5% up to 49.93%, curing the deep sensitivity collapse.",
             "High Presence Accuracy: Achieved 87.03% presence accuracy, proving through-wall RF occupancy detection.",
             "Both Metrics Validated: Demonstrates both high overall accuracy and rigorous class-balanced Macro-F1 across unseen human subjects."
         ])],
         """Speaker 3: Slide 18 presents our definitive master comparison table across all 6 LOSO folds, reporting both Overall Accuracy and Macro-F1. 
For Presence Detection, our SE-TCN achieves 87.03% accuracy, reaching 94.7% on Subject 6. 
For Postural State Recognition, SE-TCN achieves 56.50% accuracy, reaching 78.4% on Subject 6 with 85% walking recall. 
Most importantly, for Fall Detection, SE-TCN nearly doubles fall sensitivity from 26.5% up to 49.93%, reaching 66.7% on cross-session afternoon folds and catching 147 real falls directly from raw RF signals! This proves the architectural efficacy of our deep learning design."""
        ),

        # Slide 19: Fall Alarm Chain
        ("The Calibrated Fall Alarm Chain Architecture (Decision D-051)", "Fall Alarm Engineering", "Speaker 4",
         [("Continuous Stream Decision Chain", "Moving Beyond Isolated Window Testing", [
             "The Reality Gap: Testing isolated windows does not reflect reality. In real life, a streaming engine processes continuous overlapping windows.",
             "Binary Fall Detector: Dedicated Binary SVM-RBF (fall vs rest) with Platt (sigmoid) calibration fitted strictly on inner training folds.",
             "Nested Threshold Tuning: Threshold θ (0.30–0.95) and sliding window rule (k-of-n) optimized on inner training LOSO streams.",
             "Adopted Production Rule: Alarm triggered if ≥ 2 of the last 3 windows have P(fall) ≥ 0.50.",
             "Alarm Cooldown: 10-second lockout timer prevents duplicate burst alarms following an initial trigger."
         ]),
          ("Empirical Fall Chain Performance", "Evaluation on 202 Real Continuous Takes", [
             "Falls Caught: 21 of 42 falls detected (50.0% take-level detection under strict LOSO).",
             "Look-Alike Rejection: 101 of 109 look-alike takes (sit-downs, stand-ups, picking up objects) correctly rejected without alarm!",
             "Walking False Alarm Rate: 30.3 false alarms per hour of active continuous walking.",
             "Quiet Stationary False Alarms: Just 6.4 false alarms per hour in empty or motionless rooms.",
             "Median Alarm Latency: 1.99 seconds after kinematic ground impact."
         ])],
         """Speaker 4: I am Speaker 4, Nikhil M, and I will present our live alarm engine, library trial, and system limitations. 
In a real-world deployment, human monitoring is a continuous temporal stream, not isolated windows. Under Decision D-051, we engineered an end-to-end Fall Alarm Chain using calibrated posterior probabilities. 
An emergency alarm triggers only if 2 out of 3 consecutive overlapping windows exceed a 0.50 probability threshold, followed by a 10-second cooldown. Across all 202 continuous takes, this chain caught 21 of 42 falls with a median latency of 1.99 seconds while rejecting 93% of look-alike movements."""
        ),

        # Slide 20: Firmware Pipeline
        ("Firmware Implementation: COTS ESP32-S3 Real-Time Streaming", "Firmware & Embedded Systems", "Speaker 4",
         [("Embedded Architecture Details", "ESP-IDF v5.1.2 FreeRTOS Implementation", [
             "Dual Xtensa LX7 Cores: Core 0 dedicated to Wi-Fi MAC layer and RF baseband; Core 1 handles packet formatting and DMA UART transfer.",
             "Memory Allocation: Zero-copy DMA ring buffer; CSI struct unpacked in microsecond callback to prevent FreeRTOS queue starvation.",
             "Dynamic Baud Rate: High-speed UART streaming at 921,600 baud achieves < 3.2 ms packet transfer latency.",
             "Zero Packet Corruption: Byte-level CRC32 checksum embedded in every binary frame."
         ]),
          ("Firmware Build Verification (Phase 1)", "Cryptographic Reproducibility (results/firmware/)", [
             "Git Hash Immutability: Custom firmware locked to git commit tags.",
             "Binary Footprint: Compiled ELF binary size = 892 KB, fits comfortably within 8 MB onboard flash.",
             "Stability Audit: Tested continuously for 8 hours with zero memory leaks, watchdog resets, or dropped frames."
         ])],
         """Speaker 4: Slide 20 shows our embedded firmware architecture. Running on dual-core 240 MHz ESP32-S3 microcontrollers under FreeRTOS, Core 0 handles baseband Wi-Fi packet reception while Core 1 streams CSI data over DMA-backed UART at 921,600 baud. 
This zero-copy architecture guarantees sub-4-millisecond transfer latency without dropped packets. The compiled firmware consumes under 900 KB of flash and ran for 8 continuous hours with zero watchdog resets."""
        ),

        # Slide 21: Live Software Engine
        ("Software Engine: Streaming Ingest, Quality Gates & Web UI", "Software Architecture", "Speaker 4",
         [("Real-Time Processing Pipeline", "app/engine.py Architecture (Decision D-053)", [
             "Decoupled Ingest: Ring buffer ingests 200 Hz raw packets; aligns RX1 and RX2 streams by TX sequence counter.",
             "Sliding Window Engine: Emits a 4-second window every 500 ms (0.5 s hop rate).",
             "Quality Gate (D-039): Window dropped if packet loss > 20% or gap > 100 ms.",
             "Inference Cycle: Feature extraction and model inference execute in under 67 ms, easily fitting within the 500 ms cycle budget."
         ]),
          ("Interactive Monitoring Dashboard", "app/dashboard.html & WebSocket API", [
             "Real-Time Visualization: Live subcarrier waterfall heatmap, instantaneous Doppler motion energy, and posture state indicator.",
             "Emergency Fall Alert: Visual red banner and audio alarm triggered upon positive fall chain detection.",
             "Zero Cloud Dependence: Entire web server runs locally on the host machine via lightweight Python WebSockets with zero external internet required."
         ])],
         """Speaker 4: Our software architecture is organized into a modular streaming engine. A background process continuously aligns incoming packets and generates overlapping 4-second windows every 500 ms. 
Our complete inference pipeline executes in under 67 ms on a standard laptop CPU—well below the 500 ms cycle deadline. 
A real-time WebSocket dashboard visualizes the subcarrier waterfall, Doppler energy, and triggers immediate visual and audio alerts when a fall is detected, operating 100% locally without cloud dependence."""
        ),

        # Slide 22: Live Library Deployment
        ("Real-World Deployment: Live Testing in RNSIT Library Hall", "Live Field Trial", "Speaker 4",
         [("Physical Experimental Setup", "October 23, 2026 Live Deployment", [
             "Environment: RNSIT Central Library Hall (Dimensions: 14.2 m × 9.8 m).",
             "Hardware Deployment: 1 TX node, 2 RX nodes mounted on tripods at 1.2 m height.",
             "Chairs & Walking Paths: Chair A (adjacent to RX1), Chair B (adjacent to RX2), Spot M (mattress for simulated falls), Paths 1 and 2.",
             "Ambient RF Interference: 18 active university Wi-Fi Access Points operating across 2.4 GHz channels 1, 6, and 11."
         ]),
          ("Pre-Deployment Verification", "Phase 5 System Checks", [
             "60-Second Environment Baseline (D-055): Verified empty-room dynamic stability prior to testing.",
             "Decoupled Process Architecture (D-057): Engine and web dashboard executed in isolated OS processes to prevent UI rendering from blocking signal ingestion.",
             "Bit-Identical Consistency (D-054): Replaying 12 recorded takes through the live engine produced bit-identical features and model predictions compared to offline code."
         ])],
         """Speaker 4: On October 23, we conducted extensive field trials in the RNSIT Central Library hall—a large 14 by 10 meter hall with active student Wi-Fi traffic. 
We deployed our tripods, calibrated the environment with a 60-second baseline capture, and ran our decoupled engine. In Phase 5 testing, replaying raw recorded takes through our live pipeline yielded bit-identical predictions compared to offline scripts, confirming complete software reliability."""
        ),

        # Slide 23: Live Incident
        ("Engineering Under Pressure: The RF Hardware Incident", "Live Troubleshooting", "Speaker 4",
         [("The Live Failure Incident", "Trial 1 Breakdown (11:34 AM)", [
             "Symptom: During initial live walking tests, motion energy on RX2 collapsed to near zero; walking along Path 2 produced no Doppler response.",
             "Initial Suspicion: Operator suspected software buffer corruption or firmware crash.",
             "Diagnostic Inspection: Receiver 2 continued to report normal RSSI (-58 dBm) and valid packet counts at 200 Hz! Software diagnostics reported 'HEALTHY'."
         ]),
          ("Root Cause & Physical Repair", "The U.FL Connector Failure (Phase 5 Incident Report)", [
             "Physical Root Cause: The micro U.FL IPEX connector connecting the external dipole antenna to the ESP32-S3 PCB had partially unseated during tripod transport.",
             "Physics of Failure: The loose connector acted as a capacitive attenuator—allowing low-frequency RSSI carrier energy through, but destroying high-frequency phase coherence and multipath Doppler reflections!",
             "The Repair: Re-seated and mechanically secured the U.FL connector with kapton tape.",
             "Post-Repair Restoration: Phase circular std immediately dropped from 2.8 rad to 0.14 rad; dynamic motion energy surged back to expected levels."
         ])],
         """Speaker 4: Real engineering involves unexpected challenges. During our first live trial, Receiver 2 suddenly lost all Doppler sensitivity. Curiously, software showed normal RSSI and 200 Hz packet reception! 
Upon physical inspection, we discovered that the tiny U.FL antenna connector had loosened during transport. It allowed gross power through, but destroyed high-frequency phase coherence. 
We re-seated the connector, secured it with kapton tape, and phase stability was immediately restored. This demonstrated the vital difference between coarse RSSI and phase-coherent CSI."""
        ),

        # Slide 24: Live Trial Results
        ("Live Library Trial Results: Continuous 14-Minute Evaluation", "Live Performance", "Speaker 4",
         [("Continuous Trial Execution", "1658 Inference Cycles (14 Minutes)", [
             "System Health: Ran continuously for 14 minutes (1658 inference cycles) with zero crashes.",
             "Walk Across Link (Path 2, Horizontal): 37 of 42 windows correctly identified as Walk (88.1% recall)! Triggered 2 false fall alarms during fast walking (P = 0.57, 0.50).",
             "Walk Along Link (Path 1, Vertical): 6 of 51 windows correct (mostly called 'empty'; reveals Doppler blind zone).",
             "Simulated Mattress Fall: Event detected in 2 windows, but max P(fall) = 0.28 (failed to cross θ = 0.50 threshold -> NO ALARM)."
         ]),
          ("Analytical Assessment of Live Reality", "Why Live Diverged from LOSO", [
             "1. Presence Fragility: Baseline environmental drift between days caused empty rooms to occasionally register as occupied, impacting state transitions.",
             "2. Doppler Geometric Blind Spot: Moving along the line of sight (Path 1) produces minimal path-length changes, blinding the single-axis link.",
             "3. RF Co-Channel Traffic: Campus library APs operating on Channel 11 caused burst packet loss up to 8%."
         ])],
         """Speaker 4: Following the connector repair, we conducted our final 14-minute continuous live trial across 1658 consecutive inference cycles. 
When walking across the link on Path 2, the system recognized walking in 37 out of 42 windows—an 88.1% success rate! 
However, walking along the line-of-sight on Path 1 was mostly missed, revealing a geometric Doppler blind zone. 
Furthermore, while the fall was detected in 2 windows, its probability peaked at 0.28, failing to cross the 0.50 threshold to sound the alarm. Ambient library interference and presence baseline drift reduced live sensitivity relative to offline benchmarks."""
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
Our dataset comes from a single library room and 6 healthy young volunteers performing simulated falls onto a mattress at Spot M. 
We identified real technical bottlenecks: directional blind zones along the radio link, presence baseline drift across different days, and the physical vulnerability of micro-RF connectors. Acknowledging these limitations openly is essential for credible engineering research."""
        ),

        # Slide 26: Conclusion & Viva
        ("Academic Conclusion, Future Roadmap & Viva Voce Defense", "Conclusion & Defense", "Speaker 4",
         [("Key Project Achievements", "Summary of Deliverables", [
             "• Built End-to-End Testbed: Low-cost COTS ESP32-S3 transceivers capturing 114 subcarriers at 200 Hz with dual-node sequence sync.",
             "• Rigorous DSP Pipeline: Created anti-aliased, gain-normalized, phase-sanitized 32-channel dual-receiver representation.",
             "• SE-TCN Deep Learning Champion: Engineered Squeeze-and-Excitation Channel Attention and Focal Loss, doubling fall sensitivity (49.93%) over vanilla deep models and achieving 87.03% presence accuracy.",
             "• Dual-Metric Validation: Evaluated under strict 6-Fold LOSO cross-validation, reporting both Overall Accuracy and Balanced Macro-F1.",
             "• 100% Reproducible: Fully automated scripts rebuild features, train models, and verify 801 raw file checksums in 11 minutes."
         ]),
          ("Future Technical Roadmap", "Next-Generation Enhancements", [
             "1. Guided Site Calibration: 60-second automated empty-room baseline capture on startup (docs/analysis/calibration_proposal.md).",
             "2. Multi-Angle Spatial Diversity: Add a 3rd receiver at 90° azimuth to eliminate geometric Doppler blind spots.",
             "3. Automated Hardware Health Check: Implement preflight loopback tests to detect unseated RF connectors.",
             "Thank you! We now welcome questions from the examination committee."
         ])],
         """Speaker 4: In conclusion, we have designed, implemented, and validated a complete device-free human activity recognition and fall detection platform. We engineered the SE-TCN Deep Learning architecture to overcome small-data multipath overfitting, doubling fall sensitivity while maintaining 100% privacy at under $15 hardware cost. 
Our entire codebase is 100% reproducible from raw bytes in 11 minutes. 
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

    out_path = "WiFi_CSI_HAR_26_Slides_DeepLearning.pptx"
    prs.save(out_path)
    print(f"Presentation saved successfully to {out_path} ({len(prs.slides)} slides).")

if __name__ == "__main__":
    build_presentation()
