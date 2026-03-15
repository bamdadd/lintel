"""Seed data for well-known regulations.

These are templates that can be associated to projects. They cover
UK/EU financial, health, medical device, and software safety domains.
"""

from lintel.domain.types import ComplianceStatus, Regulation, RiskLevel

# fmt: off
SEED_REGULATIONS: list[Regulation] = [
    # === Healthcare & Medical Device (UK/EU) ===
    Regulation(
        regulation_id="reg-seed-mdr",
        project_id="",
        name="MDR 2017/745",
        description=(
            "EU Medical Devices Regulation. Governs the safety and"
            " performance of medical devices placed on the EU market."
        ),
        authority="EU",
        reference_url="https://eur-lex.europa.eu/eli/reg/2017/745",
        version="2017/745",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.CRITICAL,
        tags=("medical-device", "eu", "health"),
    ),
    Regulation(
        regulation_id="reg-seed-ivdr",
        project_id="",
        name="IVDR 2017/746",
        description="EU In Vitro Diagnostic Medical Devices Regulation.",
        authority="EU",
        reference_url="https://eur-lex.europa.eu/eli/reg/2017/746",
        version="2017/746",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.CRITICAL,
        tags=("medical-device", "eu", "diagnostics"),
    ),
    Regulation(
        regulation_id="reg-seed-iec62304",
        project_id="",
        name="IEC 62304",
        description=(
            "Medical device software lifecycle processes. Defines"
            " requirements for the development and maintenance of"
            " medical device software."
        ),
        authority="IEC",
        reference_url="https://www.iso.org/standard/71604.html",
        version="2006+AMD1:2015",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.CRITICAL,
        tags=("medical-device", "software", "lifecycle"),
    ),
    Regulation(
        regulation_id="reg-seed-iso14971",
        project_id="",
        name="ISO 14971",
        description=(
            "Application of risk management to medical devices."
            " Framework for identifying hazards, estimating risks,"
            " and controlling them."
        ),
        authority="ISO",
        reference_url="https://www.iso.org/standard/72704.html",
        version="2019",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.CRITICAL,
        tags=("medical-device", "risk-management"),
    ),
    Regulation(
        regulation_id="reg-seed-iso13485",
        project_id="",
        name="ISO 13485",
        description=(
            "Quality management systems for medical devices."
            " Requirements for organisations involved in the"
            " lifecycle of medical devices."
        ),
        authority="ISO",
        reference_url="https://www.iso.org/standard/59752.html",
        version="2016",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("medical-device", "quality"),
    ),
    Regulation(
        regulation_id="reg-seed-ukca-med",
        project_id="",
        name="UK Medical Devices Regulations 2002",
        description=(
            "UK domestic medical device regulations (UKCA marking)."
            " Applies to medical devices placed on the GB market."
        ),
        authority="MHRA",
        reference_url="https://www.legislation.gov.uk/uksi/2002/618",
        version="SI 2002/618",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.CRITICAL,
        tags=("medical-device", "uk", "mhra"),
    ),
    Regulation(
        regulation_id="reg-seed-hipaa",
        project_id="",
        name="HIPAA",
        description=(
            "Health Insurance Portability and Accountability Act."
            " US regulation protecting health information privacy"
            " and security."
        ),
        authority="HHS",
        reference_url="https://www.hhs.gov/hipaa",
        version="1996",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("health", "privacy", "us"),
    ),
    Regulation(
        regulation_id="reg-seed-dtb-samd",
        project_id="",
        name="NICE Evidence Standards (SaMD)",
        description=(
            "NICE evidence standards framework for digital health"
            " technologies including Software as a Medical Device."
        ),
        authority="NICE",
        reference_url=(
            "https://www.nice.org.uk/about/what-we-do/our-programmes"
            "/evidence-standards-framework-for-digital-health-technologies"
        ),
        version="2022",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("samd", "uk", "digital-health", "nice"),
    ),

    # === Data Protection & Privacy (UK/EU) ===
    Regulation(
        regulation_id="reg-seed-gdpr",
        project_id="",
        name="UK GDPR",
        description=(
            "UK General Data Protection Regulation. Governs the"
            " processing of personal data of UK residents."
        ),
        authority="ICO",
        reference_url="https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/",
        version="2018",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("privacy", "data-protection", "uk"),
    ),
    Regulation(
        regulation_id="reg-seed-dpa2018",
        project_id="",
        name="Data Protection Act 2018",
        description=(
            "UK Data Protection Act 2018, supplements the UK GDPR"
            " with domestic provisions."
        ),
        authority="ICO",
        reference_url="https://www.legislation.gov.uk/ukpga/2018/12",
        version="2018",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("privacy", "data-protection", "uk"),
    ),

    # === Financial Regulations (UK) ===
    Regulation(
        regulation_id="reg-seed-fca",
        project_id="",
        name="FCA Handbook",
        description=(
            "Financial Conduct Authority regulatory framework."
            " Covers conduct of business, prudential standards,"
            " and consumer protection."
        ),
        authority="FCA",
        reference_url="https://www.handbook.fca.org.uk/",
        version="2024",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("financial", "uk", "fca"),
    ),
    Regulation(
        regulation_id="reg-seed-psd2",
        project_id="",
        name="PSD2 (Payment Services)",
        description=(
            "Payment Services Directive 2 (as transposed into UK"
            " law). Regulates payment services including open"
            " banking and strong customer authentication."
        ),
        authority="FCA",
        reference_url="https://www.fca.org.uk/firms/payment-services-directive",
        version="2017",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("financial", "payments", "uk"),
    ),
    Regulation(
        regulation_id="reg-seed-smcr",
        project_id="",
        name="SM&CR",
        description=(
            "Senior Managers & Certification Regime. Ensures"
            " individual accountability in financial services firms."
        ),
        authority="FCA/PRA",
        reference_url="https://www.fca.org.uk/firms/senior-managers-certification-regime",
        version="2016",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("financial", "uk", "governance"),
    ),
    Regulation(
        regulation_id="reg-seed-consumer-duty",
        project_id="",
        name="Consumer Duty",
        description=(
            "FCA Consumer Duty. Requires firms to deliver good"
            " outcomes for retail customers."
        ),
        authority="FCA",
        reference_url="https://www.fca.org.uk/firms/consumer-duty",
        version="2023",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("financial", "uk", "consumer-protection"),
    ),
    Regulation(
        regulation_id="reg-seed-mifid2",
        project_id="",
        name="MiFID II (UK)",
        description=(
            "Markets in Financial Instruments Directive II as"
            " retained in UK law. Governs investment services"
            " and trading venues."
        ),
        authority="FCA",
        reference_url="https://www.fca.org.uk/markets/mifid-ii",
        version="2018",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("financial", "uk", "markets"),
    ),
    Regulation(
        regulation_id="reg-seed-aml",
        project_id="",
        name="Money Laundering Regulations 2017",
        description=(
            "UK Anti-Money Laundering regulations. Requires"
            " customer due diligence, reporting, and record-keeping."
        ),
        authority="HM Treasury",
        reference_url="https://www.legislation.gov.uk/uksi/2017/692",
        version="SI 2017/692",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.CRITICAL,
        tags=("financial", "uk", "aml", "kyc"),
    ),
    Regulation(
        regulation_id="reg-seed-dora",
        project_id="",
        name="DORA",
        description=(
            "Digital Operational Resilience Act. EU regulation on"
            " ICT risk management for financial entities (applicable"
            " to UK-EU cross-border firms)."
        ),
        authority="EU",
        reference_url="https://eur-lex.europa.eu/eli/reg/2022/2554",
        version="2022/2554",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("financial", "eu", "resilience", "ict"),
    ),

    # === Information Security ===
    Regulation(
        regulation_id="reg-seed-iso27001",
        project_id="",
        name="ISO 27001",
        description=(
            "Information security management systems. Framework for"
            " managing and protecting information assets."
        ),
        authority="ISO",
        reference_url="https://www.iso.org/standard/27001",
        version="2022",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("security", "information-security"),
    ),
    Regulation(
        regulation_id="reg-seed-soc2",
        project_id="",
        name="SOC 2",
        description=(
            "Service Organization Control 2. Trust service criteria"
            " for security, availability, processing integrity,"
            " confidentiality, and privacy."
        ),
        authority="AICPA",
        reference_url=(
            "https://www.aicpa.org/topic/audit-assurance"
            "/audit-and-assurance-greater-than-soc-2"
        ),
        version="2017",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.MEDIUM,
        tags=("security", "audit"),
    ),
    Regulation(
        regulation_id="reg-seed-nis2",
        project_id="",
        name="NIS Regulations 2018 (UK NIS)",
        description=(
            "Network and Information Systems Regulations. UK"
            " implementation of the NIS Directive for operators"
            " of essential services."
        ),
        authority="NCSC",
        reference_url="https://www.legislation.gov.uk/uksi/2018/506",
        version="SI 2018/506",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("security", "uk", "critical-infrastructure"),
    ),
    Regulation(
        regulation_id="reg-seed-cyberessentials",
        project_id="",
        name="Cyber Essentials",
        description=(
            "UK government-backed scheme for baseline cyber"
            " security controls."
        ),
        authority="NCSC",
        reference_url="https://www.cyberessentials.ncsc.gov.uk/",
        version="2024",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.MEDIUM,
        tags=("security", "uk", "baseline"),
    ),

    # === AI Regulation ===
    Regulation(
        regulation_id="reg-seed-eu-ai-act",
        project_id="",
        name="EU AI Act",
        description=(
            "Regulation laying down harmonised rules on artificial"
            " intelligence. Risk-based framework for AI systems."
        ),
        authority="EU",
        reference_url="https://eur-lex.europa.eu/eli/reg/2024/1689",
        version="2024/1689",
        status=ComplianceStatus.ACTIVE,
        risk_level=RiskLevel.HIGH,
        tags=("ai", "eu", "governance"),
    ),
]
# fmt: on
