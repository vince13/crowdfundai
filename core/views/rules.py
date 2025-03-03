from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from ..models import BusinessRule
from ..services.rules_engine import RulesEngine
from ..decorators.admin_required import admin_required
import json

@admin_required
def rules_dashboard(request):
    """View for rules management dashboard"""
    rules = {
        'investment': BusinessRule.get_rules_by_type('investment'),
        'app_submission': BusinessRule.get_rules_by_type('app_submission'),
        'user': BusinessRule.get_rules_by_type('user'),
        'moderation': BusinessRule.get_rules_by_type('moderation')
    }
    return render(request, 'core/admin/rules/dashboard.html', {
        'rules': rules,
        'rule_types': BusinessRule.RULE_TYPES
    })

@admin_required
def edit_rule(request, rule_type, rule_id=None):
    """Edit or create a business rule"""
    if rule_id:
        rule = get_object_or_404(BusinessRule, id=rule_id)
    else:
        rule = BusinessRule(rule_type=rule_type)

    if request.method == 'POST':
        try:
            rule.name = request.POST.get('name')
            rule.value = json.loads(request.POST.get('value'))
            rule.description = request.POST.get('description')
            rule.is_active = request.POST.get('is_active') == 'on'
            rule.save()

            messages.success(request, 'Rule saved successfully')
            return redirect('core:rules_dashboard')
        except json.JSONDecodeError:
            messages.error(request, 'Invalid JSON format for rule value')
        except Exception as e:
            messages.error(request, f'Error saving rule: {str(e)}')

    return render(request, 'core/admin/rules/edit.html', {
        'rule': rule,
        'rule_types': BusinessRule.RULE_TYPES
    })

@admin_required
def delete_rule(request, rule_id):
    """Delete a business rule"""
    if request.method == 'POST':
        rule = get_object_or_404(BusinessRule, id=rule_id)
        rule.delete()
        messages.success(request, 'Rule deleted successfully')
    return redirect('core:rules_dashboard')

@admin_required
def test_rule(request):
    """Test a rule with sample context"""
    if request.method == 'POST':
        try:
            rule_type = request.POST.get('rule_type')
            context = json.loads(request.POST.get('context'))
            
            result, message = RulesEngine.evaluate(rule_type, context)
            return JsonResponse({
                'success': result,
                'message': message
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })

    return JsonResponse({'error': 'Invalid request method'}) 