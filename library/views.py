from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone

from .models import Reference, Collection, ModuleLink, ZoteroAccount
from .forms import ReferenceForm, CollectionForm, ZoteroAccountForm, BibTexImportForm
from .bibtex import parse_bibtex
from .zotero_sync import sync_account


@login_required
def dashboard(request):
    """Library-Dashboard: Überblick über alle Referenzen."""
    refs = Reference.objects.filter(owner=request.user)

    stats = {
        "total": refs.count(),
        "unread": refs.filter(status="unread").count(),
        "reading": refs.filter(status="reading").count(),
        "read": refs.filter(status="read").count(),
        "cited": refs.filter(status="cited").count(),
    }
    stats["progress_percent"] = int(100 * (stats["read"] + stats["cited"]) / stats["total"]) if stats["total"] else 0

    collections = Collection.objects.filter(owner=request.user).annotate(
        count=Count("references")
    ).order_by("-count")

    latest = refs.order_by("-added_at")[:8]
    by_year = (refs.exclude(year__isnull=True)
                  .values("year").annotate(c=Count("id"))
                  .order_by("-year"))[:10]

    module_stats = (ModuleLink.objects.filter(reference__owner=request.user)
                    .values("module_code", "module_title")
                    .annotate(c=Count("id"))
                    .order_by("module_code"))

    try:
        zotero = ZoteroAccount.objects.get(owner=request.user)
    except ZoteroAccount.DoesNotExist:
        zotero = None

    return render(request, "library/dashboard.html", {
        "stats": stats,
        "collections": collections,
        "latest": latest,
        "by_year": by_year,
        "module_stats": module_stats,
        "zotero": zotero,
    })


@login_required
def reference_list(request):
    qs = Reference.objects.filter(owner=request.user)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(authors__icontains=q) |
            Q(abstract__icontains=q) | Q(notes__icontains=q) |
            Q(bibtex_key__icontains=q) | Q(tags__icontains=q)
        )

    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)

    coll = request.GET.get("collection", "")
    if coll:
        qs = qs.filter(collection_id=coll)

    year = request.GET.get("year", "")
    if year:
        qs = qs.filter(year=year)

    collections = Collection.objects.filter(owner=request.user)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "library/reference_list.html", {
        "page": page,
        "collections": collections,
        "q": q,
        "status": status,
        "coll": coll,
        "year": year,
        "status_choices": Reference.STATUS_CHOICES,
    })


@login_required
def reference_detail(request, pk):
    ref = get_object_or_404(Reference, pk=pk, owner=request.user)
    module_links = ref.module_links.all()
    return render(request, "library/reference_detail.html", {
        "ref": ref,
        "module_links": module_links,
    })


@login_required
def reference_add(request):
    if request.method == "POST":
        form = ReferenceForm(request.POST)
        if form.is_valid():
            ref = form.save(commit=False)
            ref.owner = request.user
            ref.save()
            messages.success(request, f"Referenz [{ref.bibtex_key}] gespeichert.")
            return redirect(ref.get_absolute_url())
    else:
        form = ReferenceForm()
    form.fields["collection"].queryset = Collection.objects.filter(owner=request.user)
    return render(request, "library/reference_form.html", {"form": form, "title": "Neue Referenz"})


@login_required
def reference_edit(request, pk):
    ref = get_object_or_404(Reference, pk=pk, owner=request.user)
    if request.method == "POST":
        form = ReferenceForm(request.POST, instance=ref)
        if form.is_valid():
            form.save()
            messages.success(request, "Referenz aktualisiert.")
            return redirect(ref.get_absolute_url())
    else:
        form = ReferenceForm(instance=ref)
    form.fields["collection"].queryset = Collection.objects.filter(owner=request.user)
    return render(request, "library/reference_form.html", {"form": form, "title": "Referenz bearbeiten"})


@login_required
@require_http_methods(["POST"])
def reference_delete(request, pk):
    ref = get_object_or_404(Reference, pk=pk, owner=request.user)
    bib = ref.bibtex_key
    ref.delete()
    messages.success(request, f"Referenz [{bib}] gelöscht.")
    return redirect("library:reference_list")


@login_required
def bibtex_import(request):
    if request.method == "POST":
        form = BibTexImportForm(request.POST, request.FILES)
        if form.is_valid():
            text = ""
            if form.cleaned_data.get("file"):
                text = form.cleaned_data["file"].read().decode("utf-8")
            elif form.cleaned_data.get("text"):
                text = form.cleaned_data["text"]

            collection = form.cleaned_data.get("collection")
            entries = parse_bibtex(text)

            created, updated = 0, 0
            for key, e in entries.items():
                authors = e.get("author", "").replace(" and ", "; ")
                year_raw = e.get("year", "").strip()
                year_int = int(year_raw) if year_raw.isdigit() else None

                defaults = {
                    "owner": request.user,
                    "collection": collection,
                    "entry_type": e.get("type", "misc").lower(),
                    "title": e.get("title", "")[:500],
                    "authors": authors[:500],
                    "year": year_int,
                    "journal": e.get("journal", "")[:300],
                    "publisher": e.get("publisher", "")[:300],
                    "volume": e.get("volume", "")[:50],
                    "issue": e.get("number", "")[:50],
                    "pages": e.get("pages", "").replace("--", "–")[:50],
                    "doi": e.get("doi", "")[:200],
                    "isbn": e.get("isbn", "")[:50],
                    "abstract": e.get("abstract", ""),
                    "notes": e.get("note", ""),
                    "raw_bibtex": e.get("_raw", ""),
                }
                obj, was_new = Reference.objects.update_or_create(
                    owner=request.user, bibtex_key=key, defaults=defaults)
                if was_new:
                    created += 1
                else:
                    updated += 1

            messages.success(request, f"Import fertig: {created} neu, {updated} aktualisiert.")
            return redirect("library:dashboard")
    else:
        form = BibTexImportForm()
        form.fields["collection"].queryset = Collection.objects.filter(owner=request.user)

    return render(request, "library/bibtex_import.html", {"form": form})


@login_required
def collection_list(request):
    collections = Collection.objects.filter(owner=request.user).annotate(
        count=Count("references")
    ).order_by("-updated_at")
    return render(request, "library/collection_list.html", {"collections": collections})


@login_required
def collection_detail(request, pk):
    coll = get_object_or_404(Collection, pk=pk, owner=request.user)
    qs = coll.references.all()

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(authors__icontains=q) |
            Q(abstract__icontains=q) | Q(notes__icontains=q) |
            Q(bibtex_key__icontains=q) | Q(tags__icontains=q)
        )

    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)

    qs = qs.order_by("-year", "title")

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "library/collection_detail.html", {
        "collection": coll,
        "page": page,
        "q": q,
        "status": status,
        "status_choices": Reference.STATUS_CHOICES,
    })


@login_required
def collection_add(request):
    if request.method == "POST":
        form = CollectionForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.owner = request.user
            c.save()
            messages.success(request, f"Sammlung '{c.name}' angelegt.")
            return redirect(c.get_absolute_url())
    else:
        form = CollectionForm()
    return render(request, "library/collection_form.html", {"form": form, "title": "Neue Sammlung"})


@login_required
@require_http_methods(["POST"])
def zotero_sync_now(request):
    try:
        account = ZoteroAccount.objects.get(owner=request.user)
    except ZoteroAccount.DoesNotExist:
        messages.error(request, "Kein Zotero-Zugang konfiguriert.")
        return redirect("library:zotero_settings")
    try:
        stats = sync_account(account, collection_name="Zotero-Sync")
        messages.success(
            request,
            f"Zotero-Sync erfolgreich: {stats['created']} neu, "
            f"{stats['updated']} aktualisiert, {stats['skipped']} übersprungen "
            f"(in {stats['pages']} Seiten).")
    except Exception as e:
        messages.error(request, f"Zotero-Sync fehlgeschlagen: {e}")
    return redirect("library:dashboard")


@login_required
def zotero_settings(request):
    try:
        account = ZoteroAccount.objects.get(owner=request.user)
    except ZoteroAccount.DoesNotExist:
        account = None

    if request.method == "POST":
        form = ZoteroAccountForm(request.POST, instance=account)
        if form.is_valid():
            a = form.save(commit=False)
            a.owner = request.user
            a.save()
            messages.success(request, "Zotero-Zugang gespeichert.")
            return redirect("library:dashboard")
    else:
        form = ZoteroAccountForm(instance=account)

    return render(request, "library/zotero_settings.html", {"form": form, "account": account})
