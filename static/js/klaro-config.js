// Klaro! Cookie Consent Konfiguration für Workloom
// https://klaro.org/docs/getting-started

var klaroConfig = {
    // Version für Cache-Busting bei Config-Änderungen
    version: 1,

    // Element an das der Modal angehängt wird
    elementID: 'klaro',

    // Styling
    styling: {
        theme: ['light', 'bottom', 'wide'],
    },

    // Kein Overlay über die Seite
    noAutoLoad: false,

    // HTML-Inhalt in Beschreibungen erlauben
    htmlTexts: true,

    // Beim ersten Besuch Modal anzeigen (nicht nur Banner)
    mustConsent: false,

    // Opt-out standardmäßig deaktiviert (DSGVO-konform)
    acceptAll: true,

    // Cookie-Name für Consent-Speicherung
    cookieName: 'klaro',

    // Cookie-Ablauf in Tagen
    cookieExpiresAfterDays: 365,

    // Standardmäßig alle optionalen Services deaktiviert
    default: false,

    // Keine versteckten/required Dienste automatisch aktivieren
    hideDeclineAll: false,
    hideLearnMore: false,

    // Gruppierung von Services
    groupByPurpose: true,

    // Storage-Methode
    storageMethod: 'cookie',

    // Callback wenn Consent geändert wird
    callback: function(consent, service) {
        // Seite neu laden wenn Statistik-Consent geändert wird
        if (service && service.name === 'statistics') {
            // Cookie für Server-Side Tracking setzen
            if (consent) {
                document.cookie = 'cookie_consent_statistics=true; path=/; max-age=31536000; SameSite=Lax';
            } else {
                document.cookie = 'cookie_consent_statistics=false; path=/; max-age=31536000; SameSite=Lax';
            }
        }
    },

    // Deutsche Übersetzungen
    translations: {
        zz: {
            privacyPolicyUrl: '/datenschutz/',
        },
        de: {
            privacyPolicyUrl: '/datenschutz/',
            consentModal: {
                title: 'Cookie-Einstellungen',
                description: 'Wir nutzen Cookies und ähnliche Technologien, um dir die bestmögliche Nutzung unserer Website zu ermöglichen. Einige sind technisch notwendig, andere helfen uns, die Website zu verbessern.',
            },
            consentNotice: {
                title: 'Cookie-Einstellungen',
                description: 'Wir nutzen Cookies für den Betrieb der Website und zur Analyse. Du kannst selbst entscheiden, welche Cookies du zulassen möchtest.',
                changeDescription: 'Es gab Änderungen seit deinem letzten Besuch. Bitte aktualisiere deine Einstellungen.',
                learnMore: 'Mehr erfahren',
            },
            ok: 'Alle akzeptieren',
            save: 'Auswahl speichern',
            decline: 'Nur notwendige',
            close: 'Schließen',
            acceptAll: 'Alle akzeptieren',
            acceptSelected: 'Auswahl speichern',
            declineAll: 'Alle ablehnen',
            service: {
                disableAll: {
                    title: 'Alle Services (de)aktivieren',
                    description: 'Nutze diesen Schalter, um alle Services zu (de)aktivieren.',
                },
                optOut: {
                    title: '(Opt-out)',
                    description: 'Dieser Service ist standardmäßig aktiviert (du kannst ihn aber deaktivieren).',
                },
                required: {
                    title: '(erforderlich)',
                    description: 'Dieser Service ist für die Nutzung der Website erforderlich.',
                },
                purposes: {
                    essential: 'Notwendig',
                    functional: 'Funktional',
                    statistics: 'Statistik',
                    marketing: 'Marketing',
                },
                purpose: 'Zweck',
            },
            purposes: {
                essential: {
                    title: 'Notwendige Cookies',
                    description: 'Diese Cookies sind für den Betrieb der Website unbedingt erforderlich.',
                },
                statistics: {
                    title: 'Statistik',
                    description: 'Diese Cookies helfen uns zu verstehen, wie Besucher mit unserer Website interagieren.',
                },
            },
            poweredBy: '',
        },
    },

    // Service-Definitionen
    services: [
        {
            name: 'essential',
            title: 'Technisch notwendige Cookies',
            purposes: ['essential'],
            required: true,
            default: true,
            description: 'Diese Cookies sind für den Betrieb der Website unbedingt erforderlich und können nicht deaktiviert werden.',
            cookies: [
                ['sessionid', '/', 'workloom.de'],
                ['csrftoken', '/', 'workloom.de'],
            ],
            translations: {
                de: {
                    title: 'Technisch notwendige Cookies',
                    description: 'Diese Cookies sind für den Betrieb der Website unbedingt erforderlich: Session-Verwaltung und CSRF-Schutz.',
                },
            },
        },
        {
            name: 'statistics',
            title: 'Statistik-Cookies',
            purposes: ['statistics'],
            required: false,
            default: false,
            optOut: false,
            onlyOnce: false,
            description: 'Anonymisierte Nutzungsstatistiken zur Verbesserung der Website.',
            cookies: [
                ['cookie_consent_statistics', '/', 'workloom.de'],
            ],
            translations: {
                de: {
                    title: 'Statistik',
                    description: 'Mit deiner Einwilligung erfassen wir anonymisierte Nutzungsdaten (besuchte Seiten, Browser, Gerätetyp), um unsere Website zu verbessern. Es werden keine Daten an Dritte weitergegeben.',
                },
            },
            callback: function(consent, service) {
                // Zusätzlich Cookie setzen für Server-Side Check
                if (consent) {
                    document.cookie = 'cookie_consent_statistics=true; path=/; max-age=31536000; SameSite=Lax';
                } else {
                    document.cookie = 'cookie_consent_statistics=false; path=/; max-age=31536000; SameSite=Lax';
                }
            },
        },
    ],
};
