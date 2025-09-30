from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from ...models import PageVisit, ErrorLog, PerformanceMetric, RealTimeVisitor
from ...views import analyze_traffic_sources, analyze_device_stats


class Command(BaseCommand):
    help = 'Sendet automatische Statistik-Alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='daily',
            help='Alert type: daily, weekly, or spike'
        )

    def handle(self, *args, **options):
        alert_type = options['type']

        if alert_type == 'daily':
            self.send_daily_summary()
        elif alert_type == 'weekly':
            self.send_weekly_summary()
        elif alert_type == 'spike':
            self.check_traffic_spikes()
        elif alert_type == 'errors':
            self.check_error_alerts()

    def send_daily_summary(self):
        """Sendet tägliche Zusammenfassung"""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Sammle Daten für gestern
        yesterday_visits = PageVisit.objects.filter(visit_time__date=yesterday).count()
        yesterday_unique = PageVisit.objects.filter(
            visit_time__date=yesterday
        ).values('ip_address').distinct().count()

        # Vergleich mit dem Tag davor
        day_before = yesterday - timedelta(days=1)
        day_before_visits = PageVisit.objects.filter(visit_time__date=day_before).count()

        change_percent = 0
        if day_before_visits > 0:
            change_percent = ((yesterday_visits - day_before_visits) / day_before_visits) * 100

        # Email zusammenstellen
        subject = f"📊 Täglicher Stats-Report - {yesterday.strftime('%d.%m.%Y')}"

        message = f"""
        🎯 Täglicher Website-Report für {yesterday.strftime('%d.%m.%Y')}

        📈 TRAFFIC ÜBERSICHT
        • Seitenaufrufe: {yesterday_visits:,}
        • Unique Besucher: {yesterday_unique:,}
        • Veränderung zum Vortag: {change_percent:+.1f}%

        🔍 QUICK FACTS
        • Aktuell online: {RealTimeVisitor.objects.filter(last_seen__gte=timezone.now() - timedelta(minutes=5)).count()}
        • Errors gestern: {ErrorLog.objects.filter(timestamp__date=yesterday).count()}

        🚀 STATUS
        {self.get_status_emoji(change_percent)} Trend: {"Aufwärts" if change_percent > 0 else "Abwärts" if change_percent < 0 else "Stabil"}

        📊 Vollständige Statistiken: http://127.0.0.1:8000/stats/
        """

        self.send_alert_email(subject, message)
        self.stdout.write(
            self.style.SUCCESS(f'Daily summary sent for {yesterday}')
        )

    def send_weekly_summary(self):
        """Sendet wöchentliche Zusammenfassung"""
        today = timezone.now().date()
        last_week_start = today - timedelta(days=7)

        # Wöchentliche Daten
        week_visits = PageVisit.objects.filter(visit_time__date__gte=last_week_start).count()
        week_unique = PageVisit.objects.filter(
            visit_time__date__gte=last_week_start
        ).values('ip_address').distinct().count()

        # Top Traffic Sources
        traffic_sources = analyze_traffic_sources(last_week_start)
        top_sources = traffic_sources[:3]

        # Device Stats
        device_stats = analyze_device_stats(last_week_start)

        subject = f"📊 Wöchentlicher Stats-Report - KW {today.isocalendar()[1]}"

        message = f"""
        🎯 Wöchentlicher Website-Report (Letzte 7 Tage)

        📈 TRAFFIC ÜBERSICHT
        • Seitenaufrufe: {week_visits:,}
        • Unique Besucher: {week_unique:,}
        • Durchschnitt/Tag: {week_visits//7:,}

        🌐 TOP TRAFFIC QUELLEN
        """

        for i, source in enumerate(top_sources, 1):
            message += f"• {i}. {source.get('name', 'Unbekannt')}: {source.get('count', 0)} Besucher\n        "

        message += f"""

        📱 DEVICE BREAKDOWN
        • Mobile: {sum(d['count'] for d in device_stats.get('devices', []) if d.get('name', '').lower() == 'mobile')}
        • Desktop: {sum(d['count'] for d in device_stats.get('devices', []) if d.get('name', '').lower() == 'desktop')}
        • Tablet: {sum(d['count'] for d in device_stats.get('devices', []) if d.get('name', '').lower() == 'tablet')}

        📊 Vollständige Statistiken: http://127.0.0.1:8000/stats/
        """

        self.send_alert_email(subject, message)
        self.stdout.write(
            self.style.SUCCESS(f'Weekly summary sent')
        )

    def check_traffic_spikes(self):
        """Überprüft auf Traffic-Spikes"""
        now = timezone.now()
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)

        # Besucher der letzten Stunde
        hour_visits = PageVisit.objects.filter(visit_time__gte=last_hour).count()

        # Durchschnitt der letzten 24 Stunden (pro Stunde)
        day_visits = PageVisit.objects.filter(visit_time__gte=last_day).count()
        avg_hourly = day_visits / 24

        # Spike Detection (300% über dem Durchschnitt)
        if hour_visits > avg_hourly * 3 and avg_hourly > 0:
            subject = f"🚨 Traffic-Spike erkannt!"

            message = f"""
            🔥 TRAFFIC-SPIKE ALERT!

            📈 Aktuelle Stunde: {hour_visits} Besucher
            📊 Durchschnitt/Stunde: {avg_hourly:.1f}
            📈 Steigerung: {(hour_visits/avg_hourly*100):,.0f}%

            🕐 Zeit: {now.strftime('%H:%M')}

            🔍 Sofort prüfen: http://127.0.0.1:8000/stats/
            """

            self.send_alert_email(subject, message)
            self.stdout.write(
                self.style.WARNING(f'Traffic spike detected: {hour_visits} visits in last hour')
            )

    def check_error_alerts(self):
        """Überprüft auf kritische Errors"""
        last_hour = timezone.now() - timedelta(hours=1)

        # Errors der letzten Stunde
        recent_errors = ErrorLog.objects.filter(timestamp__gte=last_hour)
        error_count = recent_errors.count()

        # Alert bei mehr als 10 Errors pro Stunde
        if error_count > 10:
            error_types = recent_errors.values('error_type').distinct()

            subject = f"⚠️ Erhöhte Error-Rate erkannt!"

            message = f"""
            🚨 ERROR ALERT!

            ❌ {error_count} Errors in der letzten Stunde

            🔧 Error Types:
            """

            for error_type in error_types:
                count = recent_errors.filter(error_type=error_type['error_type']).count()
                message += f"• {error_type['error_type']}: {count}x\n            "

            message += f"""

            🔍 Sofort prüfen: http://127.0.0.1:8000/stats/
            """

            self.send_alert_email(subject, message)
            self.stdout.write(
                self.style.ERROR(f'High error rate detected: {error_count} errors in last hour')
            )

    def get_status_emoji(self, change_percent):
        """Gibt Status-Emoji basierend auf Veränderung zurück"""
        if change_percent > 10:
            return "🚀"
        elif change_percent > 0:
            return "📈"
        elif change_percent < -10:
            return "📉"
        else:
            return "📊"

    def send_alert_email(self, subject, message):
        """Sendet Alert-Email an Superuser"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # Hole alle Superuser
            superusers = User.objects.filter(is_superuser=True, email__isnull=False).exclude(email='')

            if superusers.exists():
                recipient_list = [user.email for user in superusers]

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@workloom.de'),
                    recipient_list=recipient_list,
                    fail_silently=False,
                )

                self.stdout.write(
                    self.style.SUCCESS(f'Alert email sent to {len(recipient_list)} recipients')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('No superusers with email addresses found')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to send email: {e}')
            )