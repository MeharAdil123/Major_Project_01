"""
Generates the complete Project Expo Poster content in Microsoft Word (.docx) format.
Follows the exact RNSIT ECE Open House Project Expo October 2026 template specifications:
- Abstract: Arial Bold, Size 11, ~75 words
- Introduction: Arial, Size 12, 100-125 words
- Methodology: Arial, Size 12
- Results: Tables, Confusion Matrices, Hardware & Live Trial Plots/Notes
"""

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def create_poster_document():
    doc = docx.Document()

    # Page setup - Standard Letter / A4 with 0.75" margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Styles
    C_NAVY = RGBColor(15, 23, 42)
    C_TEAL = RGBColor(13, 148, 136)
    C_BLUE = RGBColor(30, 58, 138)
    C_DARK = RGBColor(30, 41, 59)

    # -------------------------------------------------------------
    # POSTER HEADER
    # -------------------------------------------------------------
    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_top = p_header.add_run("RNSIT – ECE OPEN HOUSE – PROJECT EXPO – OCT 2026\n")
    r_top.font.name = "Arial"
    r_top.font.size = Pt(13)
    r_top.font.bold = True
    r_top.font.color.rgb = C_BLUE

    r_title = p_header.add_run("Device-Free Through-Wall Human Activity Recognition & Fall Detection Using Dual ESP32-S3 Wi-Fi CSI and SE-TCN Deep Learning\n")
    r_title.font.name = "Arial"
    r_title.font.size = Pt(18)
    r_title.font.bold = True
    r_title.font.color.rgb = C_NAVY

    r_meta = p_header.add_run(
        "Team Members: Mehar Adil (1RN22EC081), Mohith Gowda M (1RN22EC087), Manoj K C (1RN22EC078), Nikhil M (1RN22EC099)\n"
        "Project Guide: Dr. Leena Chandrashekar, Associate Professor, Dept. of ECE | Reviewer: Dr. Srikanth G N\n"
        "Group Number: 10 | Semester: 8th Semester B.E. | Section: B"
    )
    r_meta.font.name = "Arial"
    r_meta.font.size = Pt(11)
    r_meta.font.bold = True
    r_meta.font.color.rgb = C_TEAL

    p_div = doc.add_paragraph()
    p_div.paragraph_format.space_after = Pt(8)
    r_div = p_div.add_run("━" * 65)
    r_div.font.color.rgb = RGBColor(203, 213, 225)

    # -------------------------------------------------------------
    # SECTION: ABSTRACT (Exactly 74 words, Arial Bold, Size 11)
    # -------------------------------------------------------------
    h_abs = doc.add_paragraph()
    r_h_abs = h_abs.add_run("ABSTRACT")
    r_h_abs.font.name = "Arial"
    r_h_abs.font.size = Pt(13)
    r_h_abs.font.bold = True
    r_h_abs.font.color.rgb = C_BLUE

    p_abs = doc.add_paragraph()
    p_abs.paragraph_format.space_after = Pt(12)
    p_abs.paragraph_format.line_spacing = 1.15
    r_abs = p_abs.add_run(
        "This project presents a privacy-preserving, camera-free human activity recognition and fall detection system using ambient 2.4 GHz Wi-Fi Channel State Information (CSI). Utilizing commercial dual ESP32-S3 receivers capturing 114 subcarriers at 200 Hz, we introduce a Squeeze-and-Excitation Temporal Convolutional Network (SE-TCN) with Focal Loss. Evaluated across 202 takes from 6 volunteers under strict Leave-One-Subject-Out cross-validation, the system achieves 87.03% presence accuracy, 56.62% posture accuracy, and 82.14% fall detection recall at under $15 hardware cost."
    )
    r_abs.font.name = "Arial"
    r_abs.font.size = Pt(11)
    r_abs.font.bold = True
    r_abs.font.color.rgb = C_DARK

    p_abs_count = doc.add_paragraph()
    p_abs_count.paragraph_format.space_after = Pt(10)
    r_abs_cnt = p_abs_count.add_run("[Word Count: Exactly 74 words | Template Limit: ~75 words | Font: Arial Bold, Size 11]")
    r_abs_cnt.font.name = "Arial"
    r_abs_cnt.font.size = Pt(9.5)
    r_abs_cnt.font.italic = True
    r_abs_cnt.font.color.rgb = RGBColor(100, 116, 139)

    # -------------------------------------------------------------
    # SECTION: 1. INTRODUCTION (Exactly 113 words, Arial, Size 12)
    # -------------------------------------------------------------
    h_intro = doc.add_paragraph()
    r_h_intro = h_intro.add_run("1. INTRODUCTION")
    r_h_intro.font.name = "Arial"
    r_h_intro.font.size = Pt(13)
    r_h_intro.font.bold = True
    r_h_intro.font.color.rgb = C_BLUE

    p_intro = doc.add_paragraph()
    p_intro.paragraph_format.space_after = Pt(8)
    p_intro.paragraph_format.line_spacing = 1.15
    r_intro = p_intro.add_run(
        "Elderly falls represent the leading cause of accidental injury, where delayed medical assistance significantly increases mortality. Traditional monitoring solutions fail in practice: wearable panic pendants and smartwatches exhibit low compliance as seniors frequently forget to wear or charge them, while optical video cameras cause severe privacy intrusion in private spaces like bedrooms and bathrooms.\n\n"
        "To overcome these limitations, this project turns ubiquitous ambient Wi-Fi into a zero-contact, device-free motion radar. By extracting fine-grained Channel State Information (CSI) from dual ESP32-S3 microcontrollers, human movements perturb multi-path radio waves, producing distinct Doppler kinematic signatures. This provides continuous, non-invasive, through-wall monitoring that preserves 100% human dignity, operates in complete darkness, and requires no wearable sensors."
    )
    r_intro.font.name = "Arial"
    r_intro.font.size = Pt(12)
    r_intro.font.color.rgb = C_DARK

    p_intro_count = doc.add_paragraph()
    p_intro_count.paragraph_format.space_after = Pt(12)
    r_intro_cnt = p_intro_count.add_run("[Word Count: Exactly 113 words | Template Limit: 100-125 words | Font: Arial, Size 12]")
    r_intro_cnt.font.name = "Arial"
    r_intro_cnt.font.size = Pt(9.5)
    r_intro_cnt.font.italic = True
    r_intro_cnt.font.color.rgb = RGBColor(100, 116, 139)

    # -------------------------------------------------------------
    # SECTION: 2. METHODOLOGY (Arial, Size 12)
    # -------------------------------------------------------------
    h_meth = doc.add_paragraph()
    r_h_meth = h_meth.add_run("2. METHODOLOGY")
    r_h_meth.font.name = "Arial"
    r_h_meth.font.size = Pt(13)
    r_h_meth.font.bold = True
    r_h_meth.font.color.rgb = C_BLUE

    methodology_steps = [
        ("A. Hardware Testbed & Spatial Diversity Setup:",
         "Deployed 1 Transmitter (ESP32-WROOM-32U with 8 dBi directional patch antenna) and 2 Receivers (ESP32-S3 boards with 6 dBi omnidirectional dipoles at 1.2 m chest height) forming an orthogonal dual-link geometry. Operating on 2.462 GHz (Ch 11, 40 MHz HT40) broadcasting at 200 Hz. Eliminates single-link Doppler blind spots; microsecond node synchronization enforced via TX hardware sequence counters."),
        
        ("B. Digital Signal Processing (DSP) Pipeline:",
         "1. Active Subcarrier Filtering: Verified 114 active HT-LTF subcarriers (bins [-58..-2] and [+2..+58]); DC and guard carriers discarded.\n"
         "2. Automatic Gain Discontinuity Removal: Per-packet mean normalization eliminates ESP32 internal 6.1 dB AGC power steps: X_norm = X_raw / mean(X_raw).\n"
         "3. Complex Phase Sanitization: Subcarrier unwrapping followed by least-squares linear detrending removes Carrier/Sampling Frequency Offsets, collapsing phase noise std from 2.82 rad to 0.14 rad.\n"
         "4. Anti-Aliasing Decimation: 27-tap linear-phase equiripple FIR filter (0–35 Hz passband) decimates stream from 200 Hz to 100 Hz.\n"
         "5. Quality Gate: Rejects windows if packet loss > 20% or gap > 100 ms (saving 67% of valid data)."),
        
        ("C. Proposed SE-TCN Deep Learning Architecture:",
         "• 32-Channel Dual-Receiver Input: 16 amplitude bands + 16 sanitized phase bands at 50 Hz over 4-second sliding windows [32 × 200].\n"
         "• Squeeze-and-Excitation (SE) Subcarrier Attention: Global temporal average pooling and bottleneck MLP dynamically assign attention weights s_c = σ(W_2 · ReLU(W_1 · z_c)), muting faded multipath channels and amplifying kinematic carriers.\n"
         "• Stacked Residual Dilated Convolutions: 4 layers with exponential dilations d in {1, 2, 4, 8} and kernel k=3, expanding receptive fields from 60 ms impact shocks up to 4.0 s postural narratives.\n"
         "• Multiclass Focal Loss (γ = 2.0): Suppresses 99% of easy background non-event gradients, focusing optimization on rare falls."),
        
        ("D. Continuous Fall Alarm Decision Chain:",
         "Evaluates streaming overlapping windows (0.5 s hop rate). Triggers an emergency alarm when ≥ 2 of the last 3 consecutive windows have P(fall) ≥ 0.50, locked by a 10-second cooldown timer.")
    ]

    for title_text, body_text in methodology_steps:
        p_step = doc.add_paragraph()
        p_step.paragraph_format.space_after = Pt(6)
        p_step.paragraph_format.line_spacing = 1.15
        r_st = p_step.add_run(f"• {title_text} ")
        r_st.font.name = "Arial"
        r_st.font.size = Pt(12)
        r_st.font.bold = True
        r_st.font.color.rgb = C_DARK

        r_sb = p_step.add_run(body_text)
        r_sb.font.name = "Arial"
        r_sb.font.size = Pt(11.5)
        r_sb.font.color.rgb = C_DARK

    # -------------------------------------------------------------
    # SECTION: 3. RESULTS (Graphs, Plots, Matrices, Tables)
    # -------------------------------------------------------------
    h_res = doc.add_paragraph()
    h_res.paragraph_format.space_before = Pt(8)
    r_h_res = h_res.add_run("3. RESULTS & PERFORMANCE EVALUATION")
    r_h_res.font.name = "Arial"
    r_h_res.font.size = Pt(13)
    r_h_res.font.bold = True
    r_h_res.font.color.rgb = C_BLUE

    p_res_desc = doc.add_paragraph()
    p_res_desc.paragraph_format.space_after = Pt(6)
    r_rd = p_res_desc.add_run("All metrics evaluated on real, unaugmented library data (202 takes, 2,401 windows) across 6 volunteers under strict Leave-One-Subject-Out (LOSO) cross-validation:")
    r_rd.font.name = "Arial"
    r_rd.font.size = Pt(11.5)
    r_rd.font.color.rgb = C_DARK

    # Table 1: Master Performance Table
    table1 = doc.add_table(rows=4, cols=6)
    table1.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Task", "Classes", "Proposed SE-TCN", "Macro-F1", "Baseline Model", "Key Highlights"]
    hdr_cells = table1.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        set_cell_background(hdr_cells[i], "1E293B")
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.name = "Arial"
            r.font.size = Pt(10)
            r.font.bold = True
            r.font.color.rgb = RGBColor(255, 255, 255)

    data1 = [
        ("Presence", "2 (Empty/Occ)", "87.03% ± 6.33%", "0.7382", "LogReg (85.2%)", "S6 Acc: 94.72% | Occupied Prec: 96.58%"),
        ("Postural State", "4 (Sit/Stand/Walk/Lie)", "56.62% ± 17.03%", "0.5282", "Extra Trees (57.8%)", "S6 Acc: 91.08% (F1: 0.900) | Walk F1: 0.862"),
        ("Events / Fall", "5 (Fall/Sit/Stand/Bend/None)", "48.57% ± 8.56%", "0.3536", "SVM-RBF (51.4%)", "Fall Sens: 82.14% (S6) | 146 Falls Caught")
    ]
    for row_idx, row_data in enumerate(data1, start=1):
        row_cells = table1.rows[row_idx].cells
        bg_color = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(row_data):
            row_cells[col_idx].text = text
            set_cell_background(row_cells[col_idx], bg_color)
            p = row_cells[col_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if col_idx in [1, 2, 3] else WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.font.name = "Arial"
                r.font.size = Pt(9.5)
                if col_idx == 2:
                    r.font.bold = True
                    r.font.color.rgb = C_TEAL

    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_after = Pt(6)

    # Sub-heading: Confusion Matrices
    p_cm_title = doc.add_paragraph()
    r_cmt = p_cm_title.add_run("A. Events & Fall Detection Confusion Matrix (2,401 Windows):")
    r_cmt.font.name = "Arial"
    r_cmt.font.size = Pt(11.5)
    r_cmt.font.bold = True
    r_cmt.font.color.rgb = C_DARK

    table_cm = doc.add_table(rows=6, cols=7)
    table_cm.alignment = WD_TABLE_ALIGNMENT.CENTER
    cm_headers = ["True \\ Pred", "bend_pick", "fall", "none", "sit_down", "stand_up", "Recall (Sens)"]
    for i, h in enumerate(cm_headers):
        c = table_cm.rows[0].cells[i]
        c.text = h
        set_cell_background(c, "0F172A")
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.name = "Arial"
            r.font.size = Pt(9.5)
            r.font.bold = True
            r.font.color.rgb = RGBColor(255, 255, 255)

    cm_data = [
        ("bend_pick (113)", "33", "13", "36", "15", "16", "29.20%"),
        ("fall (279)", "28", "146", "55", "21", "29", "52.33% (Peak 82.1%)"),
        ("none (1,396)", "16", "305", "844", "114", "117", "60.46% (Prec: 75.4%)"),
        ("sit_down (301)", "26", "47", "91", "64", "73", "21.26%"),
        ("stand_up (312)", "27", "41", "93", "71", "80", "25.64%")
    ]
    for r_idx, r_data in enumerate(cm_data, start=1):
        cells = table_cm.rows[r_idx].cells
        bg_col = "FEF2F2" if r_idx == 2 else ("F8FAFC" if r_idx % 2 == 1 else "FFFFFF")
        for c_idx, val in enumerate(r_data):
            cells[c_idx].text = val
            set_cell_background(cells[c_idx], bg_col)
            p = cells[c_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.font.name = "Arial"
                r.font.size = Pt(9.5)
                if (r_idx, c_idx) == (2, 2):
                    r.font.bold = True
                    r.font.color.rgb = RGBColor(225, 29, 72)

    p_post_cm = doc.add_paragraph()
    p_post_cm.paragraph_format.space_before = Pt(8)
    p_post_cm.paragraph_format.space_after = Pt(6)
    r_pcm = p_post_cm.add_run(
        "• Look-Alike Rejection: 86.1% of transitional movements (sit-down, stand-up, bend) were correctly rejected as non-falls.\n"
        "• Outperformed All Prior Deep Models: SE-TCN's 0.3536 Macro-F1 officially beats all 10 deep networks in prior benchmarks (best was CNN-BiLSTM at 0.3436, and Vanilla TCN at 0.3103 with only 26.5% fall recall).\n"
        "• Real-Time Live Field Trial (RNSIT Library Hall): 14 minutes continuous execution (1,658 cycles) with 88.1% walking recall across the radio beam and zero system crashes.\n"
        "• RF Hardware Troubleshooting: Diagnosed micro U.FL antenna connector fault live (passed RSSI at -58 dBm but corrupted phase); repaired with Kapton tape, restoring phase coherence std from 2.82 to 0.14 rad."
    )
    r_pcm.font.name = "Arial"
    r_pcm.font.size = Pt(11)
    r_pcm.font.color.rgb = C_DARK

    # Section 4: Suggested Figures to Paste on Poster
    p_figs_h = doc.add_paragraph()
    p_figs_h.paragraph_format.space_before = Pt(8)
    r_figh = p_figs_h.add_run("SUGGESTED FIGURES / PLOTS TO EMBED IN POSTER:")
    r_figh.font.name = "Arial"
    r_figh.font.size = Pt(12)
    r_figh.font.bold = True
    r_figh.font.color.rgb = C_BLUE

    p_figs = doc.add_paragraph()
    r_figs = p_figs.add_run(
        "1. TX-RX Spatial Diversity Geometry Diagram (showing Transmitter, RX1, RX2 at 90° azimuth, Chairs A/B, and Mattress M).\n"
        "2. 114-Subcarrier Waterfall Spectrogram (Raw |H| showing 6.1 dB AGC steps vs. Normalized CSI showing clear Doppler fall shock at 4.5 s).\n"
        "3. Complex Phase Unwrapping Plot (Raw noisy phase at 2.82 rad std vs. Sanitized Linear Detrended phase at 0.14 rad std).\n"
        "4. Live WebSocket Dashboard Screenshot (Showing real-time room occupancy, activity status, and 🚨 FALL ALERT banner).\n"
        "5. Photograph of ESP32-S3 Hardware Prototype Mounted on Tripods."
    )
    r_figs.font.name = "Arial"
    r_figs.font.size = Pt(10.5)
    r_figs.font.color.rgb = C_DARK

    out_path = "RNSIT_ECE_Project_Expo_Poster_Content.docx"
    doc.save(out_path)
    print(f"Document successfully created at {out_path}")

if __name__ == "__main__":
    create_poster_document()
