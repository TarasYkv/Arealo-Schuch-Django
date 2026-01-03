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
                title: 'Datenschutz-Einstellungen',
                description: 'Wähle aus, welche Cookies du zulassen möchtest.',
            },
            consentNotice: {
                title: 'Cookies',
                description: 'Wir nutzen Cookies für den Betrieb und zur Verbesserung der Website.',
                changeDescription: 'Bitte aktualisiere deine Einstellungen.',
                learnMore: 'Einstellungen',
            },
            ok: 'Akzeptieren',
            save: 'Speichern',
            decline: 'Ablehnen',
            close: 'Schließen',
            acceptAll: 'Akzeptieren',
            acceptSelected: 'Speichern',
            declineAll: 'Ablehnen',
            service: {
                disableAll: {
                    title: 'Alle (de)aktivieren',
                    description: '',
                },
                optOut: {
                    title: '(Opt-out)',
                    description: '',
                },
                required: {
                    title: '(Pflicht)',
                    description: '',
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
                    title: 'Notwendig',
                    description: 'Für den Betrieb erforderlich.',
                },
                statistics: {
                    title: 'Statistik',
                    description: 'Hilft uns, die Website zu verbessern.',
                },
            },
            poweredBy: '',
        },
    },

    // Service-Definitionen
    services: [
        {
            name: 'essential',
            title: 'Notwendig',
            purposes: ['essential'],
            required: true,
            default: true,
            description: 'Session & Sicherheit',
            cookies: [
                ['sessionid', '/', 'workloom.de'],
                ['csrftoken', '/', 'workloom.de'],
                ['klaro', '/', 'workloom.de'],
            ],
            translations: {
                de: {
                    title: 'Notwendig',
                    description: 'Session-Verwaltung und Sicherheit. Kann nicht deaktiviert werden.',
                },
            },
        },
        {
            name: 'statistics',
            title: 'Statistik',
            purposes: ['statistics'],
            required: false,
            default: false,
            optOut: false,
            onlyOnce: false,
            description: 'Anonyme Nutzungsstatistiken',
            cookies: [
                ['cookie_consent_statistics', '/', 'workloom.de'],
            ],
            translations: {
                de: {
                    title: 'Statistik',
                    description: 'Anonyme Nutzungsdaten zur Verbesserung der Website. Keine Weitergabe an Dritte.',
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
