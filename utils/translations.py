"""
Comprehensive Database Value Translation System
Provides translations for ALL canonical database values displayed to users.
These values are stored in English in the database but translated for display.
"""

STATUS_TRANSLATIONS = {
    "New": {"en": "New", "zh": "新建", "de": "Neu", "fr": "Nouveau", "tr": "Yeni", "gu": "નવું"},
    "Open": {"en": "Open", "zh": "开放", "de": "Offen", "fr": "Ouvert", "tr": "Açık", "gu": "ખુલ્લું"},
    "In Progress": {"en": "In Progress", "zh": "进行中", "de": "In Bearbeitung", "fr": "En cours", "tr": "Devam ediyor", "gu": "પ્રગતિમાં"},
    "On Hold": {"en": "On Hold", "zh": "暂停", "de": "In Wartestellung", "fr": "En attente", "tr": "Beklemede", "gu": "હોલ્ડ પર"},
    "Resolved": {"en": "Resolved", "zh": "已解决", "de": "Gelöst", "fr": "Résolu", "tr": "Çözüldü", "gu": "ઉકેલાયેલ"},
    "Closed": {"en": "Closed", "zh": "已关闭", "de": "Geschlossen", "fr": "Fermé", "tr": "Kapalı", "gu": "બંધ"},
    "Pending": {"en": "Pending", "zh": "待处理", "de": "Ausstehend", "fr": "En attente", "tr": "Beklemede", "gu": "બાકી"},
    "Cancelled": {"en": "Cancelled", "zh": "已取消", "de": "Abgebrochen", "fr": "Annulé", "tr": "İptal edildi", "gu": "રદ કર્યું"},
    "Active": {"en": "Active", "zh": "活跃", "de": "Aktiv", "fr": "Actif", "tr": "Aktif", "gu": "સક્રિય"},
    "Inactive": {"en": "Inactive", "zh": "非活跃", "de": "Inaktiv", "fr": "Inactif", "tr": "Pasif", "gu": "નિષ્ક્રિય"},
}

PRIORITY_TRANSLATIONS = {
    "Low": {"en": "Low", "zh": "低", "de": "Niedrig", "fr": "Faible", "tr": "Düşük", "gu": "નીચી"},
    "Medium": {"en": "Medium", "zh": "中", "de": "Mittel", "fr": "Moyenne", "tr": "Orta", "gu": "મધ્યમ"},
    "High": {"en": "High", "zh": "高", "de": "Hoch", "fr": "Élevée", "tr": "Yüksek", "gu": "ઊંચી"},
    "Critical": {"en": "Critical", "zh": "严重", "de": "Kritisch", "fr": "Critique", "tr": "Kritik", "gu": "ગંભીર"},
}

CATEGORY_TRANSLATIONS = {
    "Hardware Issue": {"en": "Hardware Issue", "zh": "硬件问题", "de": "Hardwareproblem", "fr": "Problème matériel", "tr": "Donanım Sorunu", "gu": "હાર્ડવેર સમસ્યા"},
    "Software Issue": {"en": "Software Issue", "zh": "软件问题", "de": "Softwareproblem", "fr": "Problème logiciel", "tr": "Yazılım Sorunu", "gu": "સોફ્ટવેર સમસ્યા"},
    "Network Issue": {"en": "Network Issue", "zh": "网络问题", "de": "Netzwerkproblem", "fr": "Problème réseau", "tr": "Ağ Sorunu", "gu": "નેટવર્ક સમસ્યા"},
    "Login Issue": {"en": "Login Issue", "zh": "登录问题", "de": "Anmeldeproblem", "fr": "Problème de connexion", "tr": "Giriş Sorunu", "gu": "લૉગિન સમસ્યા"},
    "Email Issue": {"en": "Email Issue", "zh": "邮件问题", "de": "E-Mail-Problem", "fr": "Problème d'e-mail", "tr": "E-posta Sorunu", "gu": "ઈમેલ સમસ્યા"},
    "Billing": {"en": "Billing", "zh": "账单", "de": "Abrechnung", "fr": "Facturation", "tr": "Faturalandırma", "gu": "બિલિંગ"},
    "Invoice": {"en": "Invoice", "zh": "发票", "de": "Rechnung", "fr": "Facture", "tr": "Fatura", "gu": "ઇન્વોઇસ"},
    "Payment Issue": {"en": "Payment Issue", "zh": "付款问题", "de": "Zahlungsproblem", "fr": "Problème de paiement", "tr": "Ödeme Sorunu", "gu": "ચૂકવણી સમસ્યા"},
    "Employee Documents": {"en": "Employee Documents", "zh": "员工文档", "de": "Mitarbeiterdokumente", "fr": "Documents employé", "tr": "Çalışan Belgeleri", "gu": "કર્મચારી દસ્તાવેજો"},
    "Attendance": {"en": "Attendance", "zh": "考勤", "de": "Anwesenheit", "fr": "Présence", "tr": "Katılım", "gu": "હાજરી"},
    "Leave Request": {"en": "Leave Request", "zh": "请假申请", "de": "Urlaubsantrag", "fr": "Demande de congé", "tr": "İzin Talebi", "gu": "રજા વિનંતી"},
    "Asset Request": {"en": "Asset Request", "zh": "资产申请", "de": "Asset-Anfrage", "fr": "Demande d'actif", "tr": "Varlık Talebi", "gu": "એસેટ વિનંતી"},
    "ID Card": {"en": "ID Card", "zh": "身份证", "de": "Ausweis", "fr": "Carte d'identité", "tr": "Kimlik Kartı", "gu": "આઈડી કાર્ડ"},
    "Office Maintenance": {"en": "Office Maintenance", "zh": "办公维护", "de": "Bürowartung", "fr": "Maintenance du bureau", "tr": "Ofis Bakımı", "gu": "ઓફિસ જાળવણી"},
    "Facilities": {"en": "Facilities", "zh": "设施", "de": "Einrichtungen", "fr": "Installations", "tr": "Tesisler", "gu": "સુવિધાઓ"},
    "General Administration": {"en": "General Administration", "zh": "行政管理", "de": "Allgemeine Verwaltung", "fr": "Administration générale", "tr": "Genel Yönetim", "gu": "સામાન્ય વ્યવસ્થાપન"},
    "Account Issue": {"en": "Account Issue", "zh": "账户问题", "de": "Kontoproblem", "fr": "Problème de compte", "tr": "Hesap Sorunu", "gu": "એકાઉન્ટ સમસ્યા"},
    "General Query": {"en": "General Query", "zh": "一般查询", "de": "Allgemeine Anfrage", "fr": "Requête générale", "tr": "Genel Sorgu", "gu": "સામાન્ય પ્રશ્ન"},
    "Product Issue": {"en": "Product Issue", "zh": "产品问题", "de": "Produktproblem", "fr": "Problème de produit", "tr": "Ürün Sorunu", "gu": "પ્રોડક્ટ સમસ્યા"},
    "Service Issue": {"en": "Service Issue", "zh": "服务问题", "de": "Serviceproblem", "fr": "Problème de service", "tr": "Hizmet Sorunu", "gu": "સેવા સમસ્યા"},
    "Customer Complaint": {"en": "Customer Complaint", "zh": "客户投诉", "de": "Kundenbeschwerde", "fr": "Réclamation client", "tr": "Müşteri Şikayeti", "gu": "ગ્રાહક ફરિયાદ"},
    "Wi-Fi Issue": {"en": "Wi-Fi Issue", "zh": "Wi-Fi问题", "de": "Wi-Fi-Problem", "fr": "Problème Wi-Fi", "tr": "Wi-Fi Sorunu", "gu": "Wi-Fi સમસ્યા"},
    "System Access": {"en": "System Access", "zh": "系统访问", "de": "Systemzugriff", "fr": "Accès système", "tr": "Sistem Erişimi", "gu": "સિસ્ટમ ઍક્સેસ"},
    "Password Reset": {"en": "Password Reset", "zh": "密码重置", "de": "Passwort zurücksetzen", "fr": "Réinitialisation du mot de passe", "tr": "Şifre Sıfırlama", "gu": "પાસવર્ડ રીસેટ"},
    "Printer Issue": {"en": "Printer Issue", "zh": "打印机问题", "de": "Druckerproblem", "fr": "Problème d'imprimante", "tr": "Yazıcı Sorunu", "gu": "પ્રિન્ટર સમસ્યા"},
}

DEPARTMENT_TRANSLATIONS = {
    "IT Support": {"en": "IT Support", "zh": "IT支持", "de": "IT-Support", "fr": "Support informatique", "tr": "BT Destek", "gu": "IT સપોર્ટ"},
    "HR": {"en": "HR", "zh": "人力资源", "de": "Personal", "fr": "Ressources humaines", "tr": "İK", "gu": "માનવ સંસાધન"},
    "Network Team": {"en": "Network Team", "zh": "网络团队", "de": "Netzwerkteam", "fr": "Équipe réseau", "tr": "Ağ Ekibi", "gu": "નેટવર્ક ટીમ"},
    "Software Team": {"en": "Software Team", "zh": "软件团队", "de": "Softwareteam", "fr": "Équipe logicielle", "tr": "Yazılım Ekibi", "gu": "સોફ્ટવેર ટીમ"},
    "Finance": {"en": "Finance", "zh": "财务", "de": "Finanzen", "fr": "Finance", "tr": "Maliye", "gu": "નાણાં"},
    "Administration": {"en": "Administration", "zh": "行政", "de": "Verwaltung", "fr": "Administration", "tr": "Yönetim", "gu": "વ્યવસ્થાપન"},
    "Customer Support": {"en": "Customer Support", "zh": "客户支持", "de": "Kundensupport", "fr": "Support client", "tr": "Müşteri Desteği", "gu": "ગ્રાહક સપોર્ટ"},
    "Operations": {"en": "Operations", "zh": "运营", "de": "Betrieb", "fr": "Opérations", "tr": "Operasyonlar", "gu": "કામગીરી"},
    "Management": {"en": "Management", "zh": "管理", "de": "Management", "fr": "Gestion", "tr": "Yönetim", "gu": "મેનેજમેન્ટ"},
    "Technical Support": {"en": "Technical Support", "zh": "技术支持", "de": "Technischer Support", "fr": "Support technique", "tr": "Teknik Destek", "gu": "ટેકનિકલ સપોર્ટ"},
    "Development": {"en": "Development", "zh": "开发", "de": "Entwicklung", "fr": "Développement", "tr": "Geliştirme", "gu": "વિકાસ"},
    "Quality Assurance": {"en": "Quality Assurance", "zh": "质量保证", "de": "Qualitätssicherung", "fr": "Assurance qualité", "tr": "Kalite Güvencesi", "gu": "ગુણવત્તા ખાતરી"},
    "Marketing": {"en": "Marketing", "zh": "市场", "de": "Marketing", "fr": "Marketing", "tr": "Pazarlama", "gu": "માર્કેટિંગ"},
    "Sales": {"en": "Sales", "zh": "销售", "de": "Vertrieb", "fr": "Ventes", "tr": "Satış", "gu": "વેચાણ"},
    "Legal": {"en": "Legal", "zh": "法务", "de": "Recht", "fr": "Juridique", "tr": "Hukuk", "gu": "કાયદાકીય"},
    "Security": {"en": "Security", "zh": "安全", "de": "Sicherheit", "fr": "Sécurité", "tr": "Güvenlik", "gu": "સુરક્ષા"},
    "Infrastructure": {"en": "Infrastructure", "zh": "基础设施", "de": "Infrastruktur", "fr": "Infrastructure", "tr": "Altyapı", "gu": "ઇન્ફ્રાસ્ટ્રક્ચર"},
    "Database Team": {"en": "Database Team", "zh": "数据库团队", "de": "Datenbankteam", "fr": "Équipe base de données", "tr": "Veritabanı Ekibi", "gu": "ડેટાબેઝ ટીમ"},
    "Help Desk": {"en": "Help Desk", "zh": "服务台", "de": "Helpdesk", "fr": "Centre d'assistance", "tr": "Yardım Masası", "gu": "હેલ્પ ડેસ્ક"},
}

ROLE_TRANSLATIONS = {
    "Super Admin": {"en": "Super Admin", "zh": "超级管理员", "de": "Super-Administrator", "fr": "Super administrateur", "tr": "Süper Yönetici", "gu": "સુપર એડમિન"},
    "Admin": {"en": "Admin", "zh": "管理员", "de": "Administrator", "fr": "Administrateur", "tr": "Yönetici", "gu": "એડમિન"},
    "Support Manager": {"en": "Support Manager", "zh": "支持经理", "de": "Support-Manager", "fr": "Responsable support", "tr": "Destek Yöneticisi", "gu": "સપોર્ટ મેનેજર"},
    "Support Agent": {"en": "Support Agent", "zh": "支持代理", "de": "Support-Mitarbeiter", "fr": "Agent de support", "tr": "Destek Temsilcisi", "gu": "સપોર્ટ એજન્ટ"},
    "Employee": {"en": "Employee", "zh": "员工", "de": "Mitarbeiter", "fr": "Employé", "tr": "Çalışan", "gu": "કર્મચારી"},
    "Customer": {"en": "Customer", "zh": "客户", "de": "Kunde", "fr": "Client", "tr": "Müşteri", "gu": "ગ્રાહક"},
}

ROLE_DESCRIPTION_TRANSLATIONS = {
    "Full system access and configuration": {"en": "Full system access and configuration", "zh": "完整的系统访问和配置", "de": "Voller Systemzugriff und Konfiguration", "fr": "Accès complet au système et configuration", "tr": "Tam sistem erişimi ve yapılandırma", "gu": "સંપૂર્ણ સિસ્ટમ ઍક્સેસ અને રૂપરેખા"},
    "Manages organization users, roles, and settings": {"en": "Manages organization users, roles, and settings", "zh": "管理组织用户、角色和设置", "de": "Verwaltet Organisationsbenutzer, Rollen und Einstellungen", "fr": "Gère les utilisateurs, rôles et paramètres de l'organisation", "tr": "Organizasyon kullanıcılarını, rollerini ve ayarlarını yönetir", "gu": "સંસ્થાના વપરાશકર્તાઓ, ભૂમિકાઓ અને સેટિંગ્સનું સંચાલન કરે છે"},
    "Manages support operations and support agents": {"en": "Manages support operations and support agents", "zh": "管理支持运营和支持代理", "de": "Verwaltet Support-Abläufe und Support-Mitarbeiter", "fr": "Gère les opérations de support et les agents de support", "tr": "Destek operasyonlarını ve destek temsilcilerini yönetir", "gu": "સપોર્ટ કામગીરી અને સપોર્ટ એજન્ટ્સનું સંચાલન કરે છે"},
    "Handles customer tickets and inquiries": {"en": "Handles customer tickets and inquiries", "zh": "处理客户工单和查询", "de": "Bearbeitet Kundentickets und Anfragen", "fr": "Gère les tickets et demandes des clients", "tr": "Müşteri biletlerini ve sorularını işler", "gu": "ગ્રાહક ટિકિટ્સ અને પૂંછડાંને હેન્ડલ કરે છે"},
    "Internal user with limited access": {"en": "Internal user with limited access", "zh": "具有有限访问权限的内部用户", "de": "Interner Benutzer mit eingeschränktem Zugriff", "fr": "Utilisateur interne avec accès limité", "tr": "Sınırlı erişime sahip dahili kullanıcı", "gu": "મર્યાદિત ઍક્સેસ સાથે આંતરિક વપરાશકર્તા"},
    "External customer who submits tickets": {"en": "External customer who submits tickets", "zh": "提交工单的外部客户", "de": "Externer Kunde, der Tickets einreicht", "fr": "Client externe qui soumet des tickets", "tr": "Bilet gönderen harici müşteri", "gu": "ટિકિટ્સ સબમિટ કરતા બાહ્ય ગ્રાહક"},
}

SKILL_TRANSLATIONS = {
    "Network": {"en": "Network", "zh": "网络", "de": "Netzwerk", "fr": "Réseau", "tr": "Ağ", "gu": "નેટવર્ક"},
    "Hardware": {"en": "Hardware", "zh": "硬件", "de": "Hardware", "fr": "Matériel", "tr": "Donanım", "gu": "હાર્ડવેર"},
    "Software": {"en": "Software", "zh": "软件", "de": "Software", "fr": "Logiciel", "tr": "Yazılım", "gu": "સોફ્ટવેર"},
    "Printer": {"en": "Printer", "zh": "打印机", "de": "Drucker", "fr": "Imprimante", "tr": "Yazıcı", "gu": "પ્રિન્ટર"},
    "Database": {"en": "Database", "zh": "数据库", "de": "Datenbank", "fr": "Base de données", "tr": "Veritabanı", "gu": "ડેટાબેઝ"},
    "Security": {"en": "Security", "zh": "安全", "de": "Sicherheit", "fr": "Sécurité", "tr": "Güvenlik", "gu": "સુરક્ષા"},
    "Email": {"en": "Email", "zh": "邮件", "de": "E-Mail", "fr": "E-mail", "tr": "E-posta", "gu": "ઈમેલ"},
    "Cloud": {"en": "Cloud", "zh": "云", "de": "Cloud", "fr": "Cloud", "tr": "Bulut", "gu": "કાઉન્ડ"},
    "Server": {"en": "Server", "zh": "服务器", "de": "Server", "fr": "Serveur", "tr": "Sunucu", "gu": "સર્વર"},
    "Operating System": {"en": "Operating System", "zh": "操作系统", "de": "Betriebssystem", "fr": "Système d'exploitation", "tr": "İşletim Sistemi", "gu": "ઓપરેટિંગ સિસ્ટમ"},
    "Mobile": {"en": "Mobile", "zh": "移动设备", "de": "Mobil", "fr": "Mobile", "tr": "Mobil", "gu": "મોબાઇલ"},
    "Web Development": {"en": "Web Development", "zh": "Web开发", "de": "Webentwicklung", "fr": "Développement web", "tr": "Web Geliştirme", "gu": "વેબ ડેવલપમેન્ટ"},
    "Technical Support": {"en": "Technical Support", "zh": "技术支持", "de": "Technischer Support", "fr": "Support technique", "tr": "Teknik Destek", "gu": "ટેકનિકલ સપોર્ટ"},
    "Customer Service": {"en": "Customer Service", "zh": "客户服务", "de": "Kundenservice", "fr": "Service client", "tr": "Müşteri Hizmetleri", "gu": "ગ્રાહક સેવા"},
    "Troubleshooting": {"en": "Troubleshooting", "zh": "故障排除", "de": "Fehlerbehebung", "fr": "Dépannage", "tr": "Sorun Giderme", "gu": "ટ્રબલશૂટિંગ"},
    "System Administration": {"en": "System Administration", "zh": "系统管理", "de": "Systemadministration", "fr": "Administration système", "tr": "Sistem Yönetimi", "gu": "સિસ્ટમ એડમિનિસ્ટ્રેશન"},
}

AI_CONFIDENCE_TRANSLATIONS = {
    "high": {"en": "High", "zh": "高", "de": "Hoch", "fr": "Élevé", "tr": "Yüksek", "gu": "ઊંચો"},
    "medium": {"en": "Medium", "zh": "中", "de": "Mittel", "fr": "Moyen", "tr": "Orta", "gu": "મધ્યમ"},
    "low": {"en": "Low", "zh": "低", "de": "Niedrig", "fr": "Faible", "tr": "Düşük", "gu": "નીચો"},
}


def _get_locale():
    """Get the current locale from session or Babel."""
    try:
        from flask import session
        from flask_babel import get_locale as babel_get_locale
        locale = session.get('locale')
        if not locale:
            try:
                locale_obj = babel_get_locale()
                locale = str(locale_obj) if locale_obj else 'en'
            except Exception:
                locale = 'en'
        return locale
    except Exception:
        return 'en'


def _get_lang_code(locale=None):
    """Extract language code from locale string."""
    if not locale:
        locale = _get_locale()
    if locale and isinstance(locale, str):
        return locale.split('_')[0].split('-')[0]
    return 'en'


def _translate_from_map(value, translation_map):
    """Get translated value from a translation map."""
    if value is None:
        return ""
    if value in translation_map:
        lang = _get_lang_code()
        if lang in translation_map[value]:
            return translation_map[value][lang]
        if 'en' in translation_map[value]:
            return translation_map[value]['en']
    return value


def translate_value(value, value_type="auto"):
    """
    Translate a database value for display.
    
    Args:
        value: The database value to translate
        value_type: Type of value - "status", "priority", "category", 
                   "department", "role", "role_description", "skill",
                   "ai_confidence", or "auto"
    
    Returns:
        Translated string or original value if no translation found
    """
    if value is None:
        return ""

    if value_type == "auto":
        for translation_map in [
            STATUS_TRANSLATIONS, PRIORITY_TRANSLATIONS,
            CATEGORY_TRANSLATIONS, DEPARTMENT_TRANSLATIONS,
            ROLE_TRANSLATIONS, SKILL_TRANSLATIONS,
            ROLE_DESCRIPTION_TRANSLATIONS, AI_CONFIDENCE_TRANSLATIONS
        ]:
            if value in translation_map:
                return _translate_from_map(value, translation_map)
        return value
    elif value_type == "status":
        return _translate_from_map(value, STATUS_TRANSLATIONS)
    elif value_type == "priority":
        return _translate_from_map(value, PRIORITY_TRANSLATIONS)
    elif value_type == "category":
        return _translate_from_map(value, CATEGORY_TRANSLATIONS)
    elif value_type == "department":
        return _translate_from_map(value, DEPARTMENT_TRANSLATIONS)
    elif value_type == "role":
        return _translate_from_map(value, ROLE_TRANSLATIONS)
    elif value_type == "role_description":
        return _translate_from_map(value, ROLE_DESCRIPTION_TRANSLATIONS)
    elif value_type == "skill":
        return _translate_from_map(value, SKILL_TRANSLATIONS)
    elif value_type == "ai_confidence":
        return _translate_from_map(value, AI_CONFIDENCE_TRANSLATIONS)

    return value


def translate_status(value):
    """Translate a status value."""
    return translate_value(value, "status")


def translate_priority(value):
    """Translate a priority value."""
    return translate_value(value, "priority")


def translate_category(value):
    """Translate a category value."""
    return translate_value(value, "category")


def translate_department(value):
    """Translate a department name."""
    return translate_value(value, "department")


def translate_role(value):
    """Translate a role name."""
    return translate_value(value, "role")


def translate_role_description(value):
    """Translate a role description."""
    return translate_value(value, "role_description")


def translate_skill(value):
    """Translate a skill name."""
    return translate_value(value, "skill")


def translate_user_status(value):
    """Translate a user status value (Active/Inactive)."""
    return translate_value(value, "status")


def translate_ai_confidence(value):
    """Translate an AI confidence value."""
    return translate_value(value, "ai_confidence")
