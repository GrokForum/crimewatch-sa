"""Public content for the CrimeWatch SA site (edition of 20 November 2026).

Every figure row carries a fact label from the MediaWatch SA methodology and at
least one source id from SOURCES. The site builder refuses to build if a label
is not one of the five, a source id is unknown, or a row has no source.

Content rules: aggregates only. Private victims and suspects are not named.
No incident-level farm rows, no incident article links, no date-and-town
combinations for private incidents. No organised-crime figures are named.
Public officials appear only in their public role.
"""

EDITION = "20 November 2026"
LABELS = ("Proven", "Established", "Alleged", "Disputed", "Not established")

Q2_PDF = "https://www.saps.gov.za/services/downloads/2026/2026-2027_-_2nd_Quarter_WEB.pdf"

# Reviewed source register: every link on the public site must be one of these.
SOURCES = {
    "saps_q2": ("SAPS, Police Recorded Crime Statistics, Q2 2026/27 (Jul–Sep 2026), PDF", Q2_PDF, "Official"),
    "saps_q2_xlsx": ("SAPS, Q2 2026/27 workbook (RAW Data sheet)", "https://www.saps.gov.za/services/downloads/2026/2026-2027_-_2nd_Quarter_WEB.xlsx", "Official"),
    "saps_q1": ("SAPS, Q1 2026/27 (Apr–Jun 2026), PowerPoint", "https://www.saps.gov.za/services/downloads/2026/2026-2027_-_1st_Quarter_WEB.pptx", "Official"),
    "saps_q1_xlsm": ("SAPS, Q1 2026/27 workbook", "https://www.saps.gov.za/services/downloads/2026/2026-2027_-_1st_Quarter_WEB.xlsm", "Official"),
    "saps_q2_2025": ("SAPS, Q2 2025/26 (Jul–Sep 2025), PDF", "https://www.saps.gov.za/services/downloads/2025/2025-2026_-_2nd_Quarter_WEB.pdf", "Official"),
    "saps_ar_brief": ("SAPS 2025/26 annual-report briefing to Parliament, 22 Oct 2026 (PMG)", "https://static.pmg.org.za/261022SAPS_PRESENTATION_FOR_THE_SELECT_COMMIITTEE.pdf", "Official"),
    "saps_ar": ("SAPS Annual Report 2025/26 (PMG copy)", "https://static.pmg.org.za/29_Sept_Full_Annual_Report_2025_26_compressed.pdf", "Official"),
    "npa_ar": ("NPA Annual Report 2025/26 (PMG copy; the NPA URL returned HTTP 403)", "https://pmg.org.za/files/NPA-Annual_Report_2026.pdf", "Official"),
    "nw6904": ("Written reply NW6904, NPA conviction rates, 5 Jan 2026", "https://pmg.org.za/committee-question/35378/", "Official (parliamentary)"),
    "nw4573": ("Written reply NW4573, 10111 call centres, 9 Nov 2026", "https://pmg.org.za/committee-question/41697/", "Official (parliamentary)"),
    "nw6024": ("Written reply NW6024, police-station condition, 14 Nov 2025", "https://pmg.org.za/committee-question/34030/", "Official (parliamentary)"),
    "nw2957": ("Written reply NW2957, rural-community murders", "https://pmg.org.za/committee-question/32650/", "Official (parliamentary)"),
    "nw1027": ("Written reply NW1027, rural-community murders update", "https://pmg.org.za/committee-question/36460/", "Official (parliamentary)"),
    "nw4155": ("Written reply NW4155, political-killing cases", "https://pmg.org.za/committee-question/39957/", "Official (parliamentary)"),
    "gpsjs": ("Stats SA, GPSJS 2025/26 Victims of Crime (P0341)", "https://www.statssa.gov.za/publications/P0341/P03412026.pdf", "Official survey"),
    "gpsjs_media": ("Stats SA, GPSJS 2025/26 media release", "https://www.statssa.gov.za/publications/P0341/Media%20release%20_GPSJS%202025_26_29082026%20.pdf", "Official survey"),
    "dffe_wrd": ("DFFE, World Rhino Day statement, 22 Sep 2026", "https://www.gov.za/news/media-statements/forestry-fisheries-and-environment-world-rhino-day-22-sep-2026", "Official"),
    "dffe_2025": ("DFFE, ministerial statement on 2025 rhino poaching", "https://www.dffe.gov.za/mediarelease/aucamp_16%25decline_antipoaching", "Official"),
    "speech_q2": ("Gov.za, Acting Minister of Police, release of Q2 crime statistics, 20 Nov 2026", "https://www.gov.za/news/speeches/acting-minister-firoz-cachalia-release-second-quarter-crime-statistics-20-nov-2026", "Official"),
    "iol_q2": ("IOL, ‘SA records 1,600 fewer murders, but 5,590 people killed in three months’, 20 Nov 2026", "https://iol.co.za/news/crime-and-courts/2026-11-20-sa-records-1600-fewer-murders-but-5590-people-killed-in-three-months/", "News"),
    "ewn_q2": ("EWN, ‘SA continues to record decline in murders, violent crime’, 20 Nov 2026", "https://www.ewn.co.za/2026/11/20/sa-continues-to-record-decline-in-murders-violent-crime-cachalia", "News"),
    "enca_pktt": ("eNCA, political killings task teams, 20 Nov 2026", "https://www.enca.com/news-top-stories/three-provinces-three-teams-pktt-step-fight-against-political-killings", "News"),
    "gitoc": ("GI-TOC, ‘Ballots and bullets’, October 2026", "https://globalinitiative.net/wp-content/uploads/2026/10/Julian-Rademeyer-Ballots-and-bullets-Targeted-killings-and-South-Africas-2026-local-government-elections-GI-TOC-October-2026.pdf", "Civil society (research)"),
    "tlu_oct": ("TLU SA statement, 7 Oct 2026 (own register)", "https://www.tlu.co.za/plaasmoord-beklemtoon-dringende-behoefte-aan-politieke-erns-oor-landelike-veiligheid/", "Civil society"),
    "tlu_cum": ("TLU SA cumulative register PDF, Aug 2025", "https://www.tlu.co.za/wp-content/uploads/2025/08/SHORT-MURDERS-ATTACKS-STATS1990-2025-xlsx_compressed.pdf", "Civil society"),
    "afriforum_2025": ("AfriForum, Plaasmoordeverslag 2025, 21 Apr 2026 (own register)", "https://www.artikels.afriforum.co.za/wp-content/uploads/2026/04/Plaasmoordeverslag-2025-aanvalle_21-April-2026_FINAAL.pdf", "Civil society"),
    "africacheck_farm": ("Africa Check factsheet on farm-attack statistics, 2017 (method only)", "https://www.africacheck.org/fact-checks/factsheets/factsheet-statistics-farm-attacks-and-murders-south-africa", "Civil society"),
    "jewkes2002": ("Jewkes & Abrahams 2002, Social Science & Medicine 55(7) (paywalled)", "https://doi.org/10.1016/s0277-9536(01)00242-8", "Research"),
    "iss_pb72": ("ISS Policy Brief 72, November 2014 (secondary pointer only)", "https://www.files.ethz.ch/isn/185885/PolBrief72.pdf", "Research"),
    "sadhs1998": ("SADHS 1998 full report (SAMRC)", "https://www.samrc.ac.za/sites/default/files/attachments/2022-08/SADHS1998FullReport.pdf", "Official survey"),
    "war_at_home": ("Gender Links and MRC, The War at Home (Gauteng, 2010/11)", "https://www.genderlinks.org.za/uploads/files/Publications/CompleteBookWarAtHomegaurteng.pdf", "Research"),
    "rape_crisis": ("Rape Crisis Cape Town Trust, ‘The real numbers on sexual offences’", "https://rapecrisis.org.za/the-real-numbers-on-sexual-offence/", "Civil society"),
    "tracking_justice": ("Wits CALS / MRC, Tracking Justice (2008)", "https://www.wits.ac.za/cals/our-programmes/gender/rape-attrition-study/", "Research"),
    "dm_elephant": ("Daily Maverick op-ed on Kruger elephant mortality, 8 Jul 2026", "https://www.dailymaverick.co.za/article/2026-07-08-the-951-dead-elephants-in-the-kruger-park-and-a-question-everyone-should-be-asking/", "News (opinion)"),
    "methodology": ("MediaWatch SA methodology (docs/METHODOLOGY.md)", "https://github.com/GrokForum/mediawatch-sa/blob/main/docs/METHODOLOGY.md", "Method"),
    "natural_earth": ("Natural Earth admin-1 boundaries, v5.1.2 (public domain)", "https://www.naturalearthdata.com/about/terms-of-use/", "Map data"),
    "repo": ("CrimeWatch SA repository (code, data and issues)", "https://github.com/GrokForum/crimewatch-sa", "Repository"),
    "oxpeckers": (
        "Oxpeckers, wildlife and environmental crime investigations (claims only, labelled Alleged; wildlife only. Where a story publishes a primary document, cite that document)",
        "https://oxpeckers.org/",
        "Civil society (claims; Alleged; wildlife only)",
    ),
    "wc_community_safety": (
        "Western Cape Department of Police Oversight and Community Safety (official provincial; cite SAPS first for crime counts; commentary is the provincial government's position)",
        "https://www.westerncape.gov.za/community-safety",
        "Official (provincial; SAPS cited first for counts)",
    ),
}

# ---- Home page headline figures: (value, label text, detail, fact label, [sources]) ----
HEADLINES = [
    ("5,590", "Murders recorded by SAPS, Jul–Sep 2026",
     "Down 3.5% from 5,794 (−204). 5,590 ÷ 92 days = 60.8 recorded a day (arithmetic). Official ratio 8.8 per 100,000.",
     "Proven", ["saps_q2"]),
    ("9,908", "Rapes recorded by SAPS, Jul–Sep 2026",
     "Down 2.4% from 10,154. 9,908 ÷ 92 = 107.7 recorded a day (arithmetic). Official ratio 15.5 per 100,000.",
     "Proven", ["saps_q2"]),
    ("4,934", "Kidnappings recorded by SAPS, Jul–Sep 2026",
     "Up 3.4% from 4,772. Gauteng 2,600 (52.7%, arithmetic).",
     "Proven", ["saps_q2"]),
    ("7,470", "Attempted murders recorded by SAPS, Jul–Sep 2026",
     "Up 3.0% from 7,255: this series rose while murder fell.",
     "Proven", ["saps_q2"]),
    ("23,171", "Murders recorded by SAPS, 2025/26 financial year",
     "Down 9.4% from 25,573. Rate 36.72 per 100,000. 23,171 ÷ 365 = 63.5 a day (arithmetic).",
     "Proven", ["saps_ar_brief"]),
    ("9.50%", "Murder detection rate, 2025/26",
     "SAPS-recorded detection on reported charges, against a 60% target (10.13% in 2024/25). Not a share of every murder that occurred.",
     "Proven", ["saps_ar", "saps_ar_brief"]),
]

# ---- High-profile list: (type, official, civil society or survey, [ (label, text, [sources]) ]) ----
HIGH_PROFILE = [
    {
        "type": "Murder",
        "rows": [
            ("Proven", "5,590 murders recorded by SAPS in Jul–Sep 2026 (−3.5% from 5,794). Previous quarter 5,427 (Apr–Jun 2026).", ["saps_q2", "saps_q1_xlsm"]),
            ("Proven", "23,171 recorded in 2025/26; 25,573 in 2024/25; 27,590 in 2023/24 (SAPS briefing).", ["saps_ar_brief"]),
            ("Disputed", "For 2023/24 a ministerial reply gives 27,621 murders instead of 27,590. Both official figures are shown.", ["nw2957", "saps_ar_brief"]),
            ("Proven", "Per-day arithmetic: 60.8 (Q2 2026/27), 59.6 (Q1 2026/27), 63.5 (2025/26), 70.1 (2024/25). The often-quoted “about 85 a day” is above every recent official recorded daily equivalent.", ["saps_q2", "saps_ar_brief"]),
        ],
    },
    {
        "type": "Rape and sexual offences",
        "rows": [
            ("Proven", "9,908 rapes and 12,444 sexual offences recorded by SAPS in Jul–Sep 2026 (−2.4% and −2.7%). 51,608 sexual offences recorded in 2025/26.", ["saps_q2", "saps_ar_brief"]),
            ("Disputed", "“Only 1 in 9 rapes are reported” is not established as a current national rate. The primary paper usually cited (Jewkes & Abrahams 2002) is paywalled, so its exact wording and study area are unconfirmed; ISS Policy Brief 72 is only a secondary pointer to it.", ["jewkes2002", "iss_pb72"]),
            ("Established", "SADHS 1998 (women aged 15–49, Table 5.12): 15.2% of women ever forced to have sex sought help from the police, about 1 in 7. Established for 1998 only.", ["sadhs1998"]),
            ("Established", "The War at Home (Gauteng, fieldwork 2010): 1 in 25 of all rapes, and 1 in 13 of non-partner rapes, were reported to the police. Established for that Gauteng study only, not a current national rate.", ["war_at_home"]),
            ("Alleged", "Rape Crisis estimate: 645,580 sexual offences a year with 7.7% reported, built from older research and 2017 recorded-crime figures. Not a current official total.", ["rape_crisis"]),
            ("Established", "GPSJS 2025/26 cannot support a national unreported-rape total: Stats SA says sexual offences are undercounted in the survey, and its 22,000 individual incidences sit below the 51,608 already recorded by SAPS.", ["gpsjs"]),
        ],
    },
    {
        "type": "Gender-based violence",
        "rows": [
            ("Proven", "Domestic-violence-related crimes flagged by SAPS, Apr–Jun 2026: 193 murders, 425 attempted murders, 871 rapes, 125 sexual assaults, 7,134 assault GBH and 14,392 common assaults. A flagged subset, not all GBV.", ["saps_q1"]),
            ("Proven", "2025/26 contact crime against women (18+): 199,145 (−2.2%); against children: 47,581 (+1.1%).", ["saps_ar_brief"]),
            ("Established", "GPSJS 2025/26: 408,000 individuals aged 16+ experienced assault; 70.3% of female victims said the perpetrator was known to them.", ["gpsjs_media"]),
            ("Proven", "186 FCS units with a 27% vehicle shortage, described by SAPS as limiting their capacity to serve all stations.", ["saps_ar_brief"]),
        ],
    },
    {
        "type": "Kidnapping",
        "rows": [
            ("Proven", "4,934 kidnappings recorded by SAPS in Jul–Sep 2026 (+3.4%); Gauteng 2,600. Ransom demanded in 199 of a 4,637-count circumstances sample; 33 extortion-related; 15 human trafficking.", ["saps_q2"]),
            ("Proven", "7,508 arrests for kidnapping in 2025/26 (7,543 in 2024/25). No standalone detection or conviction rate for kidnapping is published.", ["saps_ar"]),
        ],
    },
    {
        "type": "Gang violence (Western Cape)",
        "rows": [
            ("Proven", "In the SAPS Q2 murder causative-factor sample (5,396 of 5,590), 261 murders were classified as gang-related, 208 of them in the Western Cape (79.7%, arithmetic).", ["saps_q2"]),
            ("Proven", "Gang-related attempted murders in the sample: 232 of 271 nationally in the Western Cape (85.6%, arithmetic). Firearm murders in the instrument sample: Western Cape 732 of 2,552.", ["saps_q2"]),
            ("Disputed", "Western Cape murder total, Jul–Sep 2026: 1,109 (provincial summary), 1,110 (age-and-sex table) or 1,113 (sum of station rows). The release does not reconcile them.", ["saps_q2", "saps_q2_xlsx"]),
            ("Not established", "SAPS publishes no station table of gang-related murders, so no station-level gang layer is shown on the heat map.", ["saps_q2"]),
        ],
    },
    {
        "type": "Farm and rural violence",
        "rows": [
            ("Proven", "SAPS Q2 2026/27: 8 attacks on rural communities (12 a year earlier) and 8 murders of the farming community (Eastern Cape 2, Free State 1, Gauteng 2, Mpumalanga 1, North West 2). Financial year to date (Apr–Sep 2026): 9 attacks and 9 murders (arithmetic from the two official packs).", ["saps_q2", "saps_q1"]),
            ("Proven", "SAPS Q2 2025/26: 12 attacks (p28) and 12 murders of the farming community (p29) of 5,794 national murders.", ["saps_q2_2025"]),
            ("Proven", "Rural-community murders in ministerial replies: 69, 50, 51, 55 and 44 for 2020/21 to 2024/25.", ["nw2957", "nw1027"]),
            ("Alleged", "TLU SA’s own register (unaudited, own definition): 27 farm murders from 1 January to 7 October 2026; 32 in 2024 and 23 in 2025.", ["tlu_oct"]),
            ("Alleged", "AfriForum’s own register, calendar 2025: 184 farm attacks and 29 farm murders.", ["afriforum_2025"]),
            ("Alleged", "TLU SA cumulative register, 1990–2025 (2025 partial): 6,600 attacks and 2,309 murders.", ["tlu_cum"]),
            ("Established", "SAPS has no standalone ‘farm attack’ crime category; qualifying incidents are flagged under the Rural Safety Strategy. Official and civil-society counts use different definitions and periods and are not added together. Where independent counts exceed the official figure for the same period, the official figure appears lower, given those definitional differences.", ["africacheck_farm", "saps_q2"]),
        ],
    },
    {
        "type": "Political killings",
        "rows": [
            ("Not established", "No official national count. SAPS said in a written reply that compiling political-killing cases since 2020 would need manual verification of individual case records.", ["nw4155"]),
            ("Alleged", "GI-TOC’s open-source database: 45 political attacks and at least 43 people killed, 1 January to 30 September 2026. Reported incidents, not adjudicated killings.", ["gitoc"]),
            ("Alleged", "At the Q2 release the National Commissioner said the KwaZulu-Natal Political Killings Task Team has made 604 arrests since it was set up, with 151 accused sentenced; Gauteng’s team made 39 arrests in eight months and the Western Cape team 6 in three months. Official statements as reported; arrest totals, not counts of killings.", ["enca_pktt"]),
        ],
    },
    {
        "type": "Rhino and other wildlife crime",
        "rows": [
            ("Proven", "352 rhinos poached in calendar 2025, down 16% from 420 in 2024; 230 in January–August 2026 against 248 in the same months of 2025.", ["dffe_2025", "dffe_wrd"]),
            ("Proven", "NPA conviction rate for environmental crime as a whole, 2025/26: 90% (483 of 537). Not a rhino-only rate; no rhino-only conviction rate is published.", ["npa_ar"]),
            ("Alleged", "SANParks data released under PAIA and reported second-hand: 951 elephant deaths in Kruger 2020–2025, 179 of them from illegal causes.", ["dm_elephant"]),
            ("Not established", "No official national totals for abalone, pangolin, lion, elephant or cycad crime were found.", ["dffe_wrd"]),
        ],
    },
]

# ---- Where reported cases end up (aggregate attrition) ----
OUTCOMES = [
    ("Murder", "23,171", "9.50% (10.13%)", "81.89%", "71% (2,431 of 3,436), NPA Annual Report Table 17. An earlier reply gave 75.3%: Disputed between the two official sources."),
    ("Sexual offences", "51,608", "63.90% (62.27%)", "78.44%", "74% (3,794 of 5,141), NPA Annual Report Table 22."),
    ("Contact crime", "630,259", "49.25% (47.55%)", "83.97%", "No single NPA contact-crime rate."),
]
OUTCOMES_SOURCES = ["saps_ar_brief", "saps_ar", "npa_ar", "nw6904"]

# ---- Media vs official gap (indicative sample, not scored findings) ----
GAP_ROWS = [
    ("Common assault and assault GBH",
     "45,861 common assault and 41,919 assault GBH in Q2: 87,780 together, 57.6% of contact crime (152,281).",
     "Almost no national stories in the sampled window were about a typical assault.",
     "omission", ["saps_q2"]),
    ("Rape and sexual offences",
     "9,908 rapes and 12,444 sexual offences in Q2.",
     "No new national rape-incident story in the sampled window; GBV appeared mainly as official totals.",
     "omission", ["saps_q2"]),
    ("Murder",
     "5,590 in Q2, mostly single incidents spread across many stations.",
     "A handful of mass-casualty or unusual cases led crime news; most recorded murders are not individually reported.",
     "framing", ["saps_q2"]),
    ("Kidnapping",
     "4,934 in Q2, up 3.4%, Gauteng 52.7%.",
     "Kidnapping did get incident coverage in the window.",
     "none fired", ["saps_q2"]),
    ("Cash-in-transit robbery",
     "36 incidents in the whole quarter.",
     "One heist and its arrests dominated crime posts and several national titles.",
     "framing", ["saps_q2"]),
    ("Farm and rural murders",
     "8 official farming-community murders in Q2 (0.14% of 5,590, arithmetic).",
     "Political and advocacy coverage far heavier than the official quarterly count. This does not settle whether official definitions under-count (Disputed).",
     "framing", ["saps_q2"]),
    ("Attempted murder",
     "7,470 in Q2, up 3.0% while murder fell.",
     "Not a theme in sampled stories except as charges alongside murders.",
     "omission", ["saps_q2"]),
]

FACTUAL_ERRORS = [
    ("IOL headline and body: “1,600 fewer murders” year on year.", ["iol_q2"]),
    ("EWN standfirst and body: “more than 1,600 fewer murders”.", ["ewn_q2"]),
    ("Acting Minister’s Q2 speech: “over 1 600 fewer murders than the same period last year”.", ["speech_q2"]),
]
FACTUAL_ERROR_OFFICIAL = ("Proven", "Official SAPS table: 5,590 recorded against 5,794, a decline of 204 (−3.5%). The 5,590 count is right; the 1,600 decline is not supported by the official table.", ["saps_q2"])

METHOD_RULES = [
    "No invented numbers. Every figure links to its source. Where a figure could not be checked against a fetched source it is marked Not established.",
    "Official and civil-society figures sit side by side with period and definition, and are never added together or reconciled into one ‘true’ count.",
    "SAPS and NPA wording and statistics record what was charged, counted or classified, not what happened. SAPS quarterly figures are police-recorded crime (92 days in Jul–Sep 2026).",
    "Fact labels follow the MediaWatch SA methodology: Proven, Established, Alleged, Disputed and Not established. Media coverage observations use only that method’s driver names. A misreported statistic is a factual_error.",
    "Calculated figures (per-day equivalents, shares, rates per 100,000 not printed by SAPS) are labelled as arithmetic and show the inputs.",
    "Historical studies are not multiplied by current counts or extrapolated beyond their period.",
    "Only free public content is used to judge coverage.",
]

METHOD_POPIA = [
    "Private victims and suspects appear only as totals. No names, addresses, phone numbers or photographs of private people.",
    "On our own pages, private people are masked or described anonymously, for example “a farmer and his wife”.",
    "We may link to an external site that itself exposes personal information. The exposure is theirs, and we only report, mask and reference.",
    "Every fact has a reference.",
    "We are not responsible for anything published by anyone else, including personal information.",
    "Public figures, officials, police and media accounts can be named.",
    "Maps and tables go no finer than a police station: province, police district and station only, never a street, farm or victim location.",
    "Incident-level farm-attack lists are not published here; the site uses official counts and civil-society register totals only.",
    "Public officials appear only in their public role.",
    "The focus is on victims and reducing their number, not on naming organised-crime figures.",
    "A privacy request can be sent to privacy@grokforum.site.",
]

CHECKS_TEXT = [
    "AI research assistants working under a human owner draft the figures and the code. Where a bot derived a number, the page says it is arithmetic from the official counts and shows the inputs.",
    "The work is checked by a researcher, by source reviewers, and by an independent critic. New sources that are not major official or news sources are reviewed by two source reviewers before they are used.",
    "An external auditor, independent of the researcher, source reviewers and independent critic, audits the published site and repo. The audit is advisory and doesn't block publishing. Findings are raised as public issues on this repository, and each one we act on is noted in the commit history with the commit that fixed it.",
]

GAPS_OPEN = [
    "Court-ready rates for murder, rape, kidnapping and rhino poaching are not published by SAPS or the NPA.",
    "Kidnapping and rhino conviction rates are not published as standalone figures.",
    "The primary paper behind “1 in 9” is paywalled, so its wording and study area are unconfirmed.",
    "Official national totals for wildlife crime other than rhino are not published.",
    "The Western Cape and Eastern Cape murder totals, and the City of Cape Town and Amathole district totals, are not reconciled in the official release.",
    "SAPS publishes no station-level series for gang-related, political or farm crime, and no official police-district boundary map was verified, so districts and stations are shown as ranked tables inside each province rather than as map shapes.",
]
