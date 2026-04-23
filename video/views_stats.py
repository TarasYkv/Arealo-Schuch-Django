from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from video.models import Scene


GPU_PRICES = {
    'L40S': 1.95, 'A100-40': 2.10, 'A100': 2.50,
    'RTX6000': 3.03, 'H100': 3.95, 'H200': 4.54, 'B200': 6.25,
}

# Relative performance vs L40S (rough estimates)
GPU_PERF = {
    'L40S': 1.0, 'A100-40': 1.0, 'A100': 3.0,
    'RTX6000': 2.0, 'H100': 4.0, 'H200': 6.0, 'B200': 8.0,
}


@login_required
def render_stats(request):
    done_scenes = Scene.objects.filter(
        status='done', render_duration_sec__gt=0
    )

    total_scenes = done_scenes.count()
    total_cost = sum(s.render_cost for s in done_scenes) if total_scenes else 0

    # Stats by GPU
    gpu_stats = list(done_scenes.values('gpu_choice').annotate(
        avg_duration=Avg('render_duration_sec'),
        avg_cost=Avg('render_cost'),
        count=Count('id'),
    ).order_by('gpu_choice'))

    stats = []
    for gs in gpu_stats:
        gpu = gs['gpu_choice'] or 'L40S'
        price = GPU_PRICES.get(gpu, 1.95)
        dur = gs['avg_duration'] or 600
        stats.append({
            'gpu': gpu,
            'price_hr': price,
            'avg_duration_sec': round(dur, 1),
            'avg_duration_min': round(dur / 60, 1),
            'est_cost': round((dur / 3600) * price, 2),
            'count': gs['count'],
            'estimated': False,
        })

    # Baseline from L40S data (most common)
    l40s = [s for s in stats if s['gpu'] == 'L40S']
    if l40s:
        baseline_dur = l40s[0]['avg_duration_sec']
    else:
        baseline_dur = 600

    existing_gpus = set(s['gpu'] for s in stats)
    for gpu, price in GPU_PRICES.items():
        if gpu not in existing_gpus:
            ratio = GPU_PERF.get(gpu, 1.0)
            est_dur = baseline_dur / ratio
            stats.append({
                'gpu': gpu,
                'price_hr': price,
                'avg_duration_sec': round(est_dur, 1),
                'avg_duration_min': round(est_dur / 60, 1),
                'est_cost': round((est_dur / 3600) * price, 2),
                'count': 0,
                'estimated': True,
            })

    return JsonResponse({
        'total_scenes': total_scenes,
        'total_cost': round(total_cost, 2),
        'gpu_stats': stats,
    })
