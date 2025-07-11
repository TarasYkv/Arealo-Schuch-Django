from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, Avg, F
from django.urls import reverse_lazy
from django.utils import timezone
from datetime import datetime, timedelta
import json
from decimal import Decimal

from .models import (
    ShopifyStore, SalesData, ShippingProfile, RecurringCost, AdsCost, 
    SalesStatistics, ShopifyProduct, ProductShippingProfile
)
from .sales_forms import (
    DateRangeForm, ShippingProfileForm, RecurringCostForm, AdsCostForm,
    SalesDataImportForm, ProductCostForm, BulkProductCostForm, SalesFilterForm
)
from .sales_service import SalesDataImportService, SalesStatisticsService


@login_required
def sales_dashboard_view(request):
    """Hauptdashboard für Verkaufszahlen"""
    
    # Hole den ausgewählten Store
    store_id = request.GET.get('store')
    if store_id:
        store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    else:
        store = ShopifyStore.objects.filter(user=request.user).first()
        if not store:
            messages.error(request, "Sie haben noch keine Shopify Stores konfiguriert.")
            return redirect('shopify_manager:store_list')
        # Redirect mit Store-Parameter für konsistente URLs
        return redirect(f"{request.path}?store={store.id}")
    
    # Zeitraum-Form
    form = DateRangeForm(request.GET or None)
    
    start_date = timezone.now().date() - timedelta(days=30)
    end_date = timezone.now().date()
    
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
    
    # Konvertiere zu datetime für Statistiken
    start_datetime = timezone.datetime.combine(start_date, timezone.datetime.min.time())
    end_datetime = timezone.datetime.combine(end_date, timezone.datetime.max.time())
    
    if timezone.is_aware(start_datetime):
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = timezone.make_aware(end_datetime)
    
    # Berechne Statistiken
    stats_service = SalesStatisticsService(store)
    statistics = stats_service.calculate_statistics(start_datetime, end_datetime)
    
    # Bestseller
    bestsellers = stats_service.get_bestsellers(start_datetime, end_datetime, limit=10)
    
    # Zeitreihen-Daten für Diagramme
    time_series_data = stats_service.get_time_series_data(start_datetime, end_datetime, 'daily')
    
    # Bereite Daten für Charts vor
    chart_data = {
        'labels': [item['period'].strftime('%Y-%m-%d') for item in time_series_data],
        'revenue': [float(item['revenue']) for item in time_series_data],
        'orders': [item['orders'] for item in time_series_data],
        'quantity': [item['quantity'] for item in time_series_data],
    }
    
    # Alle Stores für Auswahl
    stores = ShopifyStore.objects.filter(user=request.user)
    
    context = {
        'store': store,
        'stores': stores,
        'form': form,
        'statistics': statistics,
        'bestsellers': bestsellers,
        'chart_data': json.dumps(chart_data),
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'shopify_manager/sales_dashboard_modern.html', context)


@login_required
def import_sales_data_view(request):
    """Import von Verkaufsdaten aus Shopify"""
    
    store_id = request.GET.get('store')
    if not store_id:
        messages.error(request, "Bitte wählen Sie einen Store aus.")
        return redirect('shopify_manager:sales_dashboard')
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    if request.method == 'POST':
        form = SalesDataImportForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            limit = form.cleaned_data['limit']
            
            # Konvertiere zu datetime
            start_datetime = timezone.datetime.combine(start_date, timezone.datetime.min.time())
            end_datetime = timezone.datetime.combine(end_date, timezone.datetime.max.time())
            
            if timezone.is_aware(start_datetime):
                start_datetime = timezone.make_aware(start_datetime)
                end_datetime = timezone.make_aware(end_datetime)
            
            # Importiere Daten
            import_service = SalesDataImportService(store)
            success, message = import_service.import_orders(start_datetime, end_datetime, limit)
            
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)
            
            return redirect('shopify_manager:sales_dashboard')
    else:
        form = SalesDataImportForm()
    
    context = {
        'form': form,
        'store': store,
    }
    
    return render(request, 'shopify_manager/import_sales_data.html', context)


class ShippingProfileListView(LoginRequiredMixin, ListView):
    """Liste der Versandprofile"""
    model = ShippingProfile
    template_name = 'shopify_manager/shipping_profiles.html'
    context_object_name = 'shipping_profiles'
    paginate_by = 20
    
    def get_queryset(self):
        store_id = self.request.GET.get('store')
        if store_id:
            return ShippingProfile.objects.filter(store_id=store_id, store__user=self.request.user)
        return ShippingProfile.objects.filter(store__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stores'] = ShopifyStore.objects.filter(user=self.request.user)
        return context


class ShippingProfileCreateView(LoginRequiredMixin, CreateView):
    """Neues Versandprofil erstellen"""
    model = ShippingProfile
    form_class = ShippingProfileForm
    template_name = 'shopify_manager/shipping_profile_form.html'
    success_url = reverse_lazy('shopify_manager:shipping_profiles')
    
    def form_valid(self, form):
        store_id = self.request.GET.get('store')
        if not store_id:
            messages.error(self.request, "Bitte wählen Sie einen Store aus.")
            return redirect('shopify_manager:shipping_profiles')
        
        store = get_object_or_404(ShopifyStore, id=store_id, user=self.request.user)
        form.instance.store = store
        
        messages.success(self.request, f'Versandprofil "{form.instance.name}" wurde erstellt.')
        return super().form_valid(form)


class ShippingProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Versandprofil bearbeiten"""
    model = ShippingProfile
    form_class = ShippingProfileForm
    template_name = 'shopify_manager/shipping_profile_form.html'
    success_url = reverse_lazy('shopify_manager:shipping_profiles')
    
    def get_queryset(self):
        return ShippingProfile.objects.filter(store__user=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, f'Versandprofil "{form.instance.name}" wurde aktualisiert.')
        return super().form_valid(form)


class ShippingProfileDeleteView(LoginRequiredMixin, DeleteView):
    """Versandprofil löschen"""
    model = ShippingProfile
    template_name = 'shopify_manager/shipping_profile_confirm_delete.html'
    success_url = reverse_lazy('shopify_manager:shipping_profiles')
    
    def get_queryset(self):
        return ShippingProfile.objects.filter(store__user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, f'Versandprofil "{self.get_object().name}" wurde gelöscht.')
        return super().delete(request, *args, **kwargs)


class RecurringCostListView(LoginRequiredMixin, ListView):
    """Liste der laufenden Kosten"""
    model = RecurringCost
    template_name = 'shopify_manager/recurring_costs.html'
    context_object_name = 'recurring_costs'
    paginate_by = 20
    
    def get_queryset(self):
        store_id = self.request.GET.get('store')
        if store_id:
            return RecurringCost.objects.filter(store_id=store_id, store__user=self.request.user)
        return RecurringCost.objects.filter(store__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stores'] = ShopifyStore.objects.filter(user=self.request.user)
        return context


class RecurringCostCreateView(LoginRequiredMixin, CreateView):
    """Neue laufende Kosten erstellen"""
    model = RecurringCost
    form_class = RecurringCostForm
    template_name = 'shopify_manager/recurring_cost_form.html'
    success_url = reverse_lazy('shopify_manager:recurring_costs')
    
    def form_valid(self, form):
        store_id = self.request.GET.get('store')
        if not store_id:
            messages.error(self.request, "Bitte wählen Sie einen Store aus.")
            return redirect('shopify_manager:recurring_costs')
        
        store = get_object_or_404(ShopifyStore, id=store_id, user=self.request.user)
        form.instance.store = store
        
        messages.success(self.request, f'Laufende Kosten "{form.instance.name}" wurden erstellt.')
        return super().form_valid(form)


class RecurringCostUpdateView(LoginRequiredMixin, UpdateView):
    """Laufende Kosten bearbeiten"""
    model = RecurringCost
    form_class = RecurringCostForm
    template_name = 'shopify_manager/recurring_cost_form.html'
    success_url = reverse_lazy('shopify_manager:recurring_costs')
    
    def get_queryset(self):
        return RecurringCost.objects.filter(store__user=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, f'Laufende Kosten "{form.instance.name}" wurden aktualisiert.')
        return super().form_valid(form)


class RecurringCostDeleteView(LoginRequiredMixin, DeleteView):
    """Laufende Kosten löschen"""
    model = RecurringCost
    template_name = 'shopify_manager/recurring_cost_confirm_delete.html'
    success_url = reverse_lazy('shopify_manager:recurring_costs')
    
    def get_queryset(self):
        return RecurringCost.objects.filter(store__user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, f'Laufende Kosten "{self.get_object().name}" wurden gelöscht.')
        return super().delete(request, *args, **kwargs)


class AdsCostListView(LoginRequiredMixin, ListView):
    """Liste der Werbekosten"""
    model = AdsCost
    template_name = 'shopify_manager/ads_costs.html'
    context_object_name = 'ads_costs'
    paginate_by = 20
    
    def get_queryset(self):
        store_id = self.request.GET.get('store')
        if store_id:
            return AdsCost.objects.filter(store_id=store_id, store__user=self.request.user)
        return AdsCost.objects.filter(store__user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stores'] = ShopifyStore.objects.filter(user=self.request.user)
        return context


class AdsCostCreateView(LoginRequiredMixin, CreateView):
    """Neue Werbekosten erstellen"""
    model = AdsCost
    form_class = AdsCostForm
    template_name = 'shopify_manager/ads_cost_form.html'
    success_url = reverse_lazy('shopify_manager:ads_costs')
    
    def form_valid(self, form):
        store_id = self.request.GET.get('store')
        if not store_id:
            messages.error(self.request, "Bitte wählen Sie einen Store aus.")
            return redirect('shopify_manager:ads_costs')
        
        store = get_object_or_404(ShopifyStore, id=store_id, user=self.request.user)
        form.instance.store = store
        
        messages.success(self.request, f'Werbekosten für "{form.instance.campaign_name}" wurden erstellt.')
        return super().form_valid(form)


class AdsCostUpdateView(LoginRequiredMixin, UpdateView):
    """Werbekosten bearbeiten"""
    model = AdsCost
    form_class = AdsCostForm
    template_name = 'shopify_manager/ads_cost_form.html'
    success_url = reverse_lazy('shopify_manager:ads_costs')
    
    def get_queryset(self):
        return AdsCost.objects.filter(store__user=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, f'Werbekosten für "{form.instance.campaign_name}" wurden aktualisiert.')
        return super().form_valid(form)


class AdsCostDeleteView(LoginRequiredMixin, DeleteView):
    """Werbekosten löschen"""
    model = AdsCost
    template_name = 'shopify_manager/ads_cost_confirm_delete.html'
    success_url = reverse_lazy('shopify_manager:ads_costs')
    
    def get_queryset(self):
        return AdsCost.objects.filter(store__user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, f'Werbekosten für "{self.get_object().campaign_name}" wurden gelöscht.')
        return super().delete(request, *args, **kwargs)


@login_required
def product_cost_management_view(request):
    """Verwaltung der Produkteinkaufspreise"""
    
    store_id = request.GET.get('store')
    if not store_id:
        messages.error(request, "Bitte wählen Sie einen Store aus.")
        return redirect('shopify_manager:sales_dashboard')
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    # Suche nach Produkten
    search_query = request.GET.get('search', '')
    products = ShopifyProduct.objects.filter(store=store)
    
    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) | 
            Q(shopify_id__icontains=search_query)
        )
    
    # Paginierung
    paginator = Paginator(products, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'store': store,
        'products': page_obj,
        'search_query': search_query,
        'stores': ShopifyStore.objects.filter(user=request.user),
    }
    
    return render(request, 'shopify_manager/product_cost_management.html', context)


@login_required
@require_http_methods(["POST"])
def update_product_cost_view(request):
    """AJAX-Endpoint für Produktkostenaktualisierung"""
    
    product_id = request.POST.get('product_id')
    cost_price = request.POST.get('cost_price')
    
    try:
        product = ShopifyProduct.objects.get(id=product_id, store__user=request.user)
        
        # Aktualisiere Einkaufspreis in allen Verkaufsdaten
        if cost_price:
            SalesData.objects.filter(product=product).update(cost_price=Decimal(cost_price))
            
            return JsonResponse({
                'success': True,
                'message': f'Einkaufspreis für {product.title} aktualisiert.'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Ungültiger Preis.'
            })
            
    except ShopifyProduct.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Produkt nicht gefunden.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Fehler: {str(e)}'
        })


@login_required
def sales_data_list_view(request):
    """Liste der Verkaufsdaten"""
    
    store_id = request.GET.get('store')
    if not store_id:
        messages.error(request, "Bitte wählen Sie einen Store aus.")
        return redirect('shopify_manager:sales_dashboard')
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    # Filter-Form
    form = SalesFilterForm(request.GET or None, store=store)
    
    sales_data = SalesData.objects.filter(store=store)
    
    if form.is_valid():
        if form.cleaned_data['start_date']:
            sales_data = sales_data.filter(order_date__date__gte=form.cleaned_data['start_date'])
        if form.cleaned_data['end_date']:
            sales_data = sales_data.filter(order_date__date__lte=form.cleaned_data['end_date'])
        if form.cleaned_data['product']:
            sales_data = sales_data.filter(product=form.cleaned_data['product'])
    
    # Paginierung
    paginator = Paginator(sales_data, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'store': store,
        'sales_data': page_obj,
        'form': form,
        'stores': ShopifyStore.objects.filter(user=request.user),
    }
    
    return render(request, 'shopify_manager/sales_data_list.html', context)


@login_required
def cost_breakdown_view(request):
    """Detaillierte Kostenaufschlüsselung"""
    
    store_id = request.GET.get('store')
    if not store_id:
        messages.error(request, "Bitte wählen Sie einen Store aus.")
        return redirect('shopify_manager:sales_dashboard')
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    # Zeitraum-Form
    form = DateRangeForm(request.GET or None)
    
    start_date = timezone.now().date() - timedelta(days=30)
    end_date = timezone.now().date()
    
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
    
    # Konvertiere zu datetime
    start_datetime = timezone.datetime.combine(start_date, timezone.datetime.min.time())
    end_datetime = timezone.datetime.combine(end_date, timezone.datetime.max.time())
    
    if timezone.is_aware(start_datetime):
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = timezone.make_aware(end_datetime)
    
    # Hole Verkaufsdaten
    sales_data = SalesData.objects.filter(
        store=store,
        order_date__range=[start_datetime, end_datetime]
    )
    
    # Berechne Kosten-Statistiken
    total_revenue = sales_data.aggregate(Sum('total_price'))['total_price__sum'] or 0
    total_orders = sales_data.count()
    
    # Beschaffungskosten aus Shopify
    total_procurement_cost = sales_data.exclude(cost_price__isnull=True).aggregate(
        total_cost=Sum('cost_price')
    )['total_cost'] or Decimal('0.00')
    
    # Versandkosten unterscheiden zwischen Shop und tatsächlichen Kosten
    total_shop_shipping = sales_data.aggregate(
        Sum('shop_shipping_cost')
    )['shop_shipping_cost__sum'] or Decimal('0.00')
    
    total_actual_shipping = sales_data.exclude(actual_shipping_cost__isnull=True).aggregate(
        Sum('actual_shipping_cost')
    )['actual_shipping_cost__sum'] or Decimal('0.00')
    
    # Versandgewinn/-verlust
    shipping_profit = total_shop_shipping - total_actual_shipping
    
    # Gebühren aus Shopify-Daten
    total_shopify_fees = sales_data.aggregate(
        Sum('shopify_fee')
    )['shopify_fee__sum'] or Decimal('0.00')
    
    total_paypal_fees = sales_data.aggregate(
        Sum('paypal_fee')
    )['paypal_fee__sum'] or Decimal('0.00')
    
    total_payment_gateway_fees = sales_data.aggregate(
        Sum('payment_gateway_fee')
    )['payment_gateway_fee__sum'] or Decimal('0.00')
    
    # Steuern aus Shopify tax_lines
    total_tax = sales_data.aggregate(
        Sum('tax_amount')
    )['tax_amount__sum'] or Decimal('0.00')
    
    # Gesamtkosten und Gewinn
    # Verwende tatsächliche Versandkosten falls verfügbar, sonst Shop-Versandkosten
    effective_shipping_cost = total_actual_shipping if total_actual_shipping > 0 else total_shop_shipping
    total_fees = total_shopify_fees + total_paypal_fees + total_payment_gateway_fees
    total_cost = total_procurement_cost + effective_shipping_cost + total_fees
    net_profit = total_revenue - total_cost - total_tax
    
    # Unique orders count for accurate per-order calculations
    unique_orders = sales_data.values('shopify_order_id').distinct().count()
    
    # Durchschnittswerte
    avg_procurement_cost = total_procurement_cost / unique_orders if unique_orders > 0 else Decimal('0.00')
    avg_procurement_per_order = total_procurement_cost / unique_orders if unique_orders > 0 else Decimal('0.00')
    avg_shipping_per_order = effective_shipping_cost / unique_orders if unique_orders > 0 else Decimal('0.00')
    avg_shopify_fees_per_order = total_shopify_fees / unique_orders if unique_orders > 0 else Decimal('0.00')
    avg_paypal_fees_per_order = total_paypal_fees / unique_orders if unique_orders > 0 else Decimal('0.00')
    avg_payment_gateway_fees_per_order = total_payment_gateway_fees / unique_orders if unique_orders > 0 else Decimal('0.00')
    avg_tax_per_order = total_tax / unique_orders if unique_orders > 0 else Decimal('0.00')
    avg_profit_per_order = net_profit / unique_orders if unique_orders > 0 else Decimal('0.00')
    
    # Prozentuale Anteile
    procurement_percentage = (total_procurement_cost / total_revenue * 100) if total_revenue > 0 else 0
    shipping_percentage = (effective_shipping_cost / total_revenue * 100) if total_revenue > 0 else 0
    shopify_fees_percentage = (total_shopify_fees / total_revenue * 100) if total_revenue > 0 else 0
    paypal_fees_percentage = (total_paypal_fees / total_revenue * 100) if total_revenue > 0 else 0
    payment_gateway_fees_percentage = (total_payment_gateway_fees / total_revenue * 100) if total_revenue > 0 else 0
    tax_percentage = (total_tax / total_revenue * 100) if total_revenue > 0 else 0
    profit_percentage = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    context = {
        'store': store,
        'form': form,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'unique_orders': unique_orders,
        'total_procurement_cost': total_procurement_cost,
        'total_shop_shipping': total_shop_shipping,
        'total_actual_shipping': total_actual_shipping,
        'effective_shipping_cost': effective_shipping_cost,
        'shipping_profit': shipping_profit,
        'total_shopify_fees': total_shopify_fees,
        'total_paypal_fees': total_paypal_fees,
        'total_payment_gateway_fees': total_payment_gateway_fees,
        'total_tax': total_tax,
        'total_fees': total_fees,
        'total_cost': total_cost,
        'net_profit': net_profit,
        'avg_procurement_cost': avg_procurement_cost,
        'avg_procurement_per_order': avg_procurement_per_order,
        'avg_shipping_per_order': avg_shipping_per_order,
        'avg_shopify_fees_per_order': avg_shopify_fees_per_order,
        'avg_paypal_fees_per_order': avg_paypal_fees_per_order,
        'avg_payment_gateway_fees_per_order': avg_payment_gateway_fees_per_order,
        'avg_tax_per_order': avg_tax_per_order,
        'avg_profit_per_order': avg_profit_per_order,
        'procurement_percentage': procurement_percentage,
        'shipping_percentage': shipping_percentage,
        'shopify_fees_percentage': shopify_fees_percentage,
        'paypal_fees_percentage': paypal_fees_percentage,
        'payment_gateway_fees_percentage': payment_gateway_fees_percentage,
        'tax_percentage': tax_percentage,
        'profit_percentage': profit_percentage,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'shopify_manager/cost_breakdown.html', context)


@login_required
def assign_shipping_profile_view(request):
    """Zuweisung von Versandprofilen zu Produkten"""
    
    store_id = request.GET.get('store')
    if not store_id:
        messages.error(request, "Bitte wählen Sie einen Store aus.")
        return redirect('shopify_manager:sales_dashboard')
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        shipping_profile_id = request.POST.get('shipping_profile_id')
        
        try:
            product = ShopifyProduct.objects.get(id=product_id, store=store)
            
            if shipping_profile_id:
                shipping_profile = ShippingProfile.objects.get(id=shipping_profile_id, store=store)
                
                # Erstelle oder aktualisiere Zuordnung
                product_shipping_profile, created = ProductShippingProfile.objects.get_or_create(
                    product=product,
                    defaults={'shipping_profile': shipping_profile}
                )
                
                if not created:
                    product_shipping_profile.shipping_profile = shipping_profile
                    product_shipping_profile.save()
                
                messages.success(request, f'Versandprofil für {product.title} zugewiesen.')
            else:
                # Entferne Zuordnung
                ProductShippingProfile.objects.filter(product=product).delete()
                messages.success(request, f'Versandprofil für {product.title} entfernt.')
                
        except (ShopifyProduct.DoesNotExist, ShippingProfile.DoesNotExist):
            messages.error(request, "Produkt oder Versandprofil nicht gefunden.")
        
        return redirect('shopify_manager:assign_shipping_profile')
    
    # Hole Produkte mit aktuellen Versandprofilen
    products = ShopifyProduct.objects.filter(store=store).select_related('shipping_profile__shipping_profile')
    shipping_profiles = ShippingProfile.objects.filter(store=store, is_active=True)
    
    # Paginierung
    paginator = Paginator(products, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'store': store,
        'products': page_obj,
        'shipping_profiles': shipping_profiles,
        'stores': ShopifyStore.objects.filter(user=request.user),
    }
    
    return render(request, 'shopify_manager/assign_shipping_profile.html', context)


@login_required
def paypal_fees_analysis_view(request):
    """Detaillierte PayPal-Gebührenanalyse aus Shopify-Daten"""
    
    store_id = request.GET.get('store')
    if not store_id:
        messages.error(request, "Bitte wählen Sie einen Store aus.")
        return redirect('shopify_manager:sales_dashboard')
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    # Zeitraum-Form
    form = DateRangeForm(request.GET or None)
    
    start_date = timezone.now().date() - timedelta(days=30)
    end_date = timezone.now().date()
    
    if form.is_valid():
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
    
    # Konvertiere zu datetime
    start_datetime = timezone.datetime.combine(start_date, timezone.datetime.min.time())
    end_datetime = timezone.datetime.combine(end_date, timezone.datetime.max.time())
    
    if timezone.is_aware(start_datetime):
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = timezone.make_aware(end_datetime)
    
    # Hole alle PayPal-Transaktionen
    paypal_sales = SalesData.objects.filter(
        store=store,
        order_date__range=[start_datetime, end_datetime]
    ).filter(
        Q(payment_gateway__icontains='paypal') | Q(paypal_fee__gt=0)
    )
    
    # Gruppiere nach Bestellungen
    paypal_orders = paypal_sales.values('shopify_order_id').annotate(
        order_total=Sum('total_price'),
        order_paypal_fee=Sum('paypal_fee'),
        items_count=Count('id')
    ).order_by('-order_date')
    
    # Berechne Gesamtstatistiken
    total_stats = paypal_sales.aggregate(
        total_revenue=Sum('total_price'),
        total_fees=Sum('paypal_fee'),
        total_orders=Count('shopify_order_id', distinct=True),
        total_items=Count('id')
    )
    
    # Berechne durchschnittliche Gebühren
    if total_stats['total_revenue'] and total_stats['total_revenue'] > 0 and total_stats['total_fees']:
        avg_fee_percentage = (total_stats['total_fees'] / total_stats['total_revenue']) * 100
    else:
        avg_fee_percentage = 0
    
    # Monatliche PayPal-Gebühren für Trend
    monthly_fees = paypal_sales.extra(
        select={'month': "strftime('%%Y-%%m', order_date)"}
    ).values('month').annotate(
        revenue=Sum('total_price'),
        fees=Sum('paypal_fee'),
        orders=Count('shopify_order_id', distinct=True)
    ).order_by('month')
    
    # Gebühren nach Betragsbereichen
    fee_ranges = [
        {'range': '0-50€', 'min': 0, 'max': 50},
        {'range': '50-100€', 'min': 50, 'max': 100},
        {'range': '100-250€', 'min': 100, 'max': 250},
        {'range': '250-500€', 'min': 250, 'max': 500},
        {'range': '500€+', 'min': 500, 'max': 999999}
    ]
    
    for fee_range in fee_ranges:
        range_data = paypal_orders.filter(
            order_total__gte=fee_range['min'],
            order_total__lt=fee_range['max']
        ).aggregate(
            count=Count('shopify_order_id'),
            total_fees=Sum('order_paypal_fee'),
            total_revenue=Sum('order_total')
        )
        fee_range.update(range_data)
        if range_data['total_revenue'] and range_data['total_revenue'] > 0:
            fee_range['avg_percentage'] = (range_data['total_fees'] / range_data['total_revenue']) * 100
        else:
            fee_range['avg_percentage'] = 0
    
    # PayPal Account-Typ Info
    paypal_config = {
        'account_type': store.paypal_account_type,
        'monthly_volume': store.paypal_monthly_volume,
        'handler_rate': store.paypal_handler_rate,
        'handler_fixed_fee': store.paypal_handler_fixed_fee
    }
    
    # Berechne potentielle Ersparnis mit Handler Account
    if store.paypal_account_type != 'handler':
        # Simuliere Handler-Gebühren
        handler_fees = Decimal('0')
        for order in paypal_orders:
            # Handler: 1.99% + 0.35€
            order_total = order['order_total'] or Decimal('0')
            simulated_fee = (order_total * Decimal('0.0199')) + Decimal('0.35')
            handler_fees += simulated_fee
        
        # Debug: Prüfe auf None-Werte
        print(f"DEBUG: total_stats = {total_stats}")
        print(f"DEBUG: total_stats['total_fees'] = {total_stats['total_fees']}")
        print(f"DEBUG: handler_fees = {handler_fees}")
        
        current_fees = total_stats['total_fees'] if total_stats['total_fees'] is not None else Decimal('0')
        handler_fees = handler_fees if handler_fees is not None else Decimal('0')
        
        print(f"DEBUG: current_fees = {current_fees}")
        print(f"DEBUG: handler_fees after check = {handler_fees}")
        
        potential_savings = current_fees - handler_fees
        print(f"DEBUG: potential_savings = {potential_savings}")
    else:
        potential_savings = Decimal('0')
    
    context = {
        'store': store,
        'form': form,
        'paypal_orders': paypal_orders[:50],  # Erste 50 Bestellungen
        'total_stats': total_stats,
        'avg_fee_percentage': avg_fee_percentage,
        'monthly_fees': list(monthly_fees),
        'fee_ranges': fee_ranges,
        'paypal_config': paypal_config,
        'potential_savings': potential_savings,
        'start_date': start_date,
        'end_date': end_date,
        'stores': ShopifyStore.objects.filter(user=request.user)
    }
    
    return render(request, 'shopify_manager/paypal_fees_analysis.html', context)


@login_required
def orders_table_view(request):
    """Detaillierte Tabelle aller Bestellungen mit Kosten und Provisionen"""
    
    # Hole den ausgewählten Store
    store_id = request.GET.get('store')
    if store_id:
        store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    else:
        store = ShopifyStore.objects.filter(user=request.user).first()
        if not store:
            messages.error(request, "Sie haben noch keine Shopify Stores konfiguriert.")
            return redirect('shopify_manager:store_list')
    
    # Filter-Formular
    filter_form = SalesFilterForm(request.GET or None)
    
    # Basis-Query
    orders = SalesData.objects.filter(store=store).select_related('product')
    
    # Filter anwenden
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('start_date'):
            orders = orders.filter(order_date__date__gte=filter_form.cleaned_data['start_date'])
        if filter_form.cleaned_data.get('end_date'):
            orders = orders.filter(order_date__date__lte=filter_form.cleaned_data['end_date'])
        if filter_form.cleaned_data.get('product'):
            orders = orders.filter(product__title__icontains=filter_form.cleaned_data['product'])
        if filter_form.cleaned_data.get('order_id'):
            orders = orders.filter(shopify_order_id=filter_form.cleaned_data['order_id'])
    
    # Sortierung
    sort_by = request.GET.get('sort', '-order_date')
    orders = orders.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(orders, 50)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    
    # Hole Google Ads Daten für die Produkte
    from .models import GoogleAdsProductData
    for order in orders_page:
        if order.product:
            # Hole die aktuellsten Google Ads Daten für dieses Produkt
            google_ads_data = GoogleAdsProductData.objects.filter(
                product=order.product,
                date__lte=order.order_date.date()
            ).order_by('-date').first()
            
            if google_ads_data:
                # Berechne anteilige Werbekosten basierend auf Conversions
                if google_ads_data.conversions > 0:
                    order.google_ads_cost = google_ads_data.cost / google_ads_data.conversions
                else:
                    order.google_ads_cost = 0
                order.google_ads_campaign = google_ads_data.campaign_name
            else:
                order.google_ads_cost = 0
                order.google_ads_campaign = None
    
    # Berechne Zusammenfassung für aktuelle Seite
    summary = {
        'total_revenue': sum(order.total_price or 0 for order in orders_page),
        'total_cost': sum((order.cost_price or 0) * order.quantity for order in orders_page),
        'total_shopify_fees': sum(order.shopify_fee or 0 for order in orders_page),
        'total_paypal_fees': sum(order.paypal_fee or 0 for order in orders_page),
        'total_payment_fees': sum(order.payment_gateway_fee or 0 for order in orders_page),
        'total_profit': sum(order.profit or 0 for order in orders_page),
    }
    
    # Alle Stores für Auswahl
    stores = ShopifyStore.objects.filter(user=request.user)
    
    context = {
        'store': store,
        'stores': stores,
        'orders': orders_page,
        'filter_form': filter_form,
        'summary': summary,
        'sort_by': sort_by,
    }
    
    return render(request, 'shopify_manager/orders_table.html', context)


@login_required
def google_ads_config_view(request):
    """Google Ads API Konfiguration"""
    
    store_id = request.GET.get('store')
    if store_id:
        store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    else:
        store = ShopifyStore.objects.filter(user=request.user).first()
        if not store:
            messages.error(request, "Sie haben noch keine Shopify Stores konfiguriert.")
            return redirect('shopify_manager:store_list')
    
    if request.method == 'POST':
        # Speichere Google Ads Konfiguration
        store.google_ads_customer_id = request.POST.get('customer_id', '')
        store.google_ads_developer_token = request.POST.get('developer_token', '')
        store.google_ads_refresh_token = request.POST.get('refresh_token', '')
        store.google_ads_client_id = request.POST.get('client_id', '')
        store.google_ads_client_secret = request.POST.get('client_secret', '')
        store.save()
        
        messages.success(request, "Google Ads Konfiguration gespeichert.")
        return redirect('shopify_manager:google_ads_sync', store_id=store.id)
    
    context = {
        'store': store,
        'stores': ShopifyStore.objects.filter(user=request.user),
    }
    
    return render(request, 'shopify_manager/google_ads_config.html', context)


@login_required
def google_ads_sync_view(request, store_id):
    """Synchronisiert Google Ads Daten"""
    
    store = get_object_or_404(ShopifyStore, id=store_id, user=request.user)
    
    if request.method == 'POST':
        try:
            from .google_ads_service import GoogleAdsService
            
            service = GoogleAdsService(store)
            days_back = int(request.POST.get('days_back', 30))
            
            success, message = service.sync_product_ads_data(days_back)
            
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)
                
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Unerwarteter Fehler: {str(e)}")
    
    # Hole letzte Sync-Daten
    from .models import GoogleAdsProductData
    last_sync = GoogleAdsProductData.objects.filter(store=store).order_by('-created_at').first()
    
    context = {
        'store': store,
        'stores': ShopifyStore.objects.filter(user=request.user),
        'last_sync': last_sync.created_at if last_sync else None,
        'has_config': all([
            store.google_ads_customer_id,
            store.google_ads_developer_token,
            store.google_ads_refresh_token,
            store.google_ads_client_id,
            store.google_ads_client_secret
        ])
    }
    
    return render(request, 'shopify_manager/google_ads_sync.html', context)