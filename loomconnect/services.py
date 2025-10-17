"""
LoomConnect Services
Business logic for matching, notifications, and statistics
"""

import logging
from typing import List, Dict, Any, Optional
from django.db.models import Q, Count, Avg
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from .models import ConnectProfile, UserSkill, UserNeed, Connection

User = get_user_model()
logger = logging.getLogger(__name__)


class MatchService:
    """Service for finding and calculating skill matches"""

    @staticmethod
    def calculate_match_score(profile1: ConnectProfile, profile2: ConnectProfile) -> int:
        """
        Calculate match score between two profiles (0-100%)
        Based on:
        - Common skills
        - Complementary skills (one offers what the other needs)
        - Skill levels
        """
        score = 0
        factors = 0

        # Get skills and needs
        profile1_skills = set(UserSkill.objects.filter(profile=profile1, is_offering=True).values_list('skill_id', flat=True))
        profile2_skills = set(UserSkill.objects.filter(profile=profile2, is_offering=True).values_list('skill_id', flat=True))

        profile1_needs = set(UserNeed.objects.filter(profile=profile1, is_active=True).values_list('skill_id', flat=True))
        profile2_needs = set(UserNeed.objects.filter(profile=profile2, is_active=True).values_list('skill_id', flat=True))

        # Factor 1: Common skills (40% weight)
        common_skills = profile1_skills.intersection(profile2_skills)
        if len(common_skills) > 0:
            score += min(40, len(common_skills) * 10)
        factors += 40

        # Factor 2: Complementary skills - Profile1 needs what Profile2 offers (30% weight)
        complementary_1 = profile1_needs.intersection(profile2_skills)
        if len(complementary_1) > 0:
            score += min(30, len(complementary_1) * 15)
        factors += 30

        # Factor 3: Complementary skills - Profile2 needs what Profile1 offers (30% weight)
        complementary_2 = profile2_needs.intersection(profile1_skills)
        if len(complementary_2) > 0:
            score += min(30, len(complementary_2) * 15)
        factors += 30

        # Normalize to 0-100
        return min(100, int((score / factors) * 100)) if factors > 0 else 0

    @staticmethod
    def find_matches_for_profile(profile: ConnectProfile, limit: int = 10, min_score: int = 30) -> List[Dict[str, Any]]:
        """
        Find best matches for a profile
        Returns list of matches with scores and details
        """
        # Get all other active, public profiles
        other_profiles = ConnectProfile.objects.filter(
            is_public=True,
            onboarding_completed=True
        ).exclude(user=profile.user)

        # Exclude already connected profiles
        connected_profiles = Connection.objects.filter(
            Q(profile_1=profile) | Q(profile_2=profile)
        ).values_list('profile_1_id', 'profile_2_id')

        connected_ids = set()
        for p1, p2 in connected_profiles:
            connected_ids.add(p1)
            connected_ids.add(p2)

        other_profiles = other_profiles.exclude(id__in=connected_ids)

        # Calculate scores and collect matches
        matches = []
        for other_profile in other_profiles:
            score = MatchService.calculate_match_score(profile, other_profile)

            if score >= min_score:
                # Get common skills
                profile_skills = set(UserSkill.objects.filter(profile=profile).values_list('skill_id', flat=True))
                other_skills = set(UserSkill.objects.filter(profile=other_profile).values_list('skill_id', flat=True))
                common_skill_ids = profile_skills.intersection(other_skills)

                from .models import Skill
                common_skills = Skill.objects.filter(id__in=common_skill_ids)

                matches.append({
                    'profile': other_profile,
                    'score': score,
                    'common_skills': list(common_skills),
                    'skill_count': UserSkill.objects.filter(profile=other_profile).count()
                })

        # Sort by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)

        return matches[:limit]

    @staticmethod
    def send_match_notification(to_profile: ConnectProfile, match_profile: ConnectProfile, match_score: int):
        """
        Send email notification about a new match
        """
        if not to_profile.notify_new_matches:
            return

        try:
            from email_templates.trigger_manager import TriggerManager

            trigger_manager = TriggerManager()
            current_site = Site.objects.get_current()

            # Get match skills
            match_skills = UserSkill.objects.filter(profile=match_profile, is_offering=True)[:5]
            match_skills_str = ', '.join([f"{us.skill.name} ({us.get_level_display()})" for us in match_skills])

            # Get common skills
            to_skills = set(UserSkill.objects.filter(profile=to_profile).values_list('skill_id', flat=True))
            match_skill_ids = set(UserSkill.objects.filter(profile=match_profile).values_list('skill_id', flat=True))
            common_skill_ids = to_skills.intersection(match_skill_ids)

            from .models import Skill
            common_skills = Skill.objects.filter(id__in=common_skill_ids)
            common_skills_str = ', '.join([s.name for s in common_skills])

            context_data = {
                'user_name': to_profile.user.get_full_name() or to_profile.user.username,
                'match_username': match_profile.user.username,
                'match_name': match_profile.user.get_full_name() or match_profile.user.username,
                'match_bio': match_profile.bio[:200] if match_profile.bio else 'Kein Profil-Text vorhanden',
                'match_skills': match_skills_str or 'Keine Skills angegeben',
                'match_profile_url': f"https://{current_site.domain}/connect/profile/{match_profile.user.username}/",
                'common_skills': common_skills_str or 'Keine gemeinsamen Skills',
                'match_score': str(match_score),
                'site_url': f"https://{current_site.domain}"
            }

            trigger_manager.fire_trigger(
                trigger_key='loomconnect_new_match',
                context_data=context_data,
                recipient_email=to_profile.user.email,
                recipient_name=to_profile.user.get_full_name(),
                sent_by=None
            )

            logger.info(f"Sent match notification to {to_profile.user.email} about {match_profile.user.username}")
        except Exception as e:
            logger.error(f"Failed to send match notification: {str(e)}")


class StatisticsService:
    """Service for gathering LoomConnect statistics"""

    @staticmethod
    def get_global_stats() -> Dict[str, Any]:
        """Get global LoomConnect statistics"""
        from .models import SkillCategory, Skill, Post, Story

        total_profiles = ConnectProfile.objects.count()
        active_profiles = ConnectProfile.objects.filter(is_public=True, onboarding_completed=True).count()
        total_connections = Connection.objects.count()
        total_skills = UserSkill.objects.count()
        total_needs = UserNeed.objects.count()

        # Most popular skills
        popular_skills = UserSkill.objects.values('skill__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Most active users (by connections)
        active_users = Connection.objects.values('profile_1__user__username').annotate(
            connection_count=Count('id')
        ).order_by('-connection_count')[:10]

        # Categories with most skills
        popular_categories = SkillCategory.objects.annotate(
            skill_count=Count('skill')
        ).order_by('-skill_count')[:10]

        return {
            'total_profiles': total_profiles,
            'active_profiles': active_profiles,
            'total_connections': total_connections,
            'total_skills': total_skills,
            'total_needs': total_needs,
            'total_posts': Post.objects.count() if hasattr(Post, 'objects') else 0,
            'total_stories': Story.objects.count() if hasattr(Story, 'objects') else 0,
            'popular_skills': list(popular_skills),
            'active_users': list(active_users),
            'popular_categories': list(popular_categories),
            'avg_connections_per_user': Connection.objects.aggregate(
                avg=Avg('profile_1__successful_connections')
            )['avg'] or 0,
            'avg_skills_per_user': UserSkill.objects.values('profile').annotate(
                count=Count('id')
            ).aggregate(avg=Avg('count'))['avg'] or 0
        }

    @staticmethod
    def get_profile_stats(profile: ConnectProfile) -> Dict[str, Any]:
        """Get statistics for a specific profile"""
        connections = Connection.objects.filter(
            Q(profile_1=profile) | Q(profile_2=profile)
        ).count()

        skills_offered = UserSkill.objects.filter(profile=profile, is_offering=True).count()
        skills_total = UserSkill.objects.filter(profile=profile).count()
        needs = UserNeed.objects.filter(profile=profile, is_active=True).count()

        return {
            'profile': profile,
            'connections': connections,
            'skills_offered': skills_offered,
            'skills_total': skills_total,
            'needs': needs,
            'profile_views': profile.profile_views_count,
            'karma_score': profile.karma_score,
            'successful_connections': profile.successful_connections
        }
