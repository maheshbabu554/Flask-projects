/**
 * main.js - Health Insurance Claims Processing Simulator
 * Client-side enhancements: Bootstrap tooltips, dynamic form filtering, and payout preview.
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Initialize all Bootstrap Tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 2. Auto-dismiss flash messages after 6 seconds
    setTimeout(function () {
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function (alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 6000);

    // 3. Dynamic Member Filtering on Claim Creation Form
    const policySelect = document.getElementById('policy_select');
    const memberSelect = document.getElementById('member_select');

    if (policySelect && memberSelect) {
        function filterMembers() {
            const selectedPolicyId = policySelect.value;
            const options = memberSelect.querySelectorAll('option');

            let hasVisible = false;
            options.forEach(function (opt) {
                if (!opt.value) {
                    opt.hidden = false;
                    return;
                }
                const optPolicyId = opt.getAttribute('data-policy-id');
                if (!selectedPolicyId || optPolicyId === selectedPolicyId) {
                    opt.hidden = false;
                    if (!hasVisible) {
                        memberSelect.value = opt.value;
                        hasVisible = true;
                    }
                } else {
                    opt.hidden = true;
                }
            });

            if (!hasVisible && options.length > 0) {
                memberSelect.value = '';
            }
        }

        policySelect.addEventListener('change', filterMembers);
        // Run once on initial load
        filterMembers();
    }

    // 4. Live Payout Calculation Preview on Approval Modal / Form
    const eligibleInput = document.getElementById('eligible_amount_input');
    const previewPayout = document.getElementById('preview_payout_amount');
    const previewDeductible = document.getElementById('preview_deductible_amount');
    const previewCopay = document.getElementById('preview_copay_amount');

    if (eligibleInput && previewPayout) {
        const deductibleLimit = parseFloat(eligibleInput.getAttribute('data-deductible') || '0');
        const copayPercent = parseFloat(eligibleInput.getAttribute('data-copay') || '0');

        function updatePayoutPreview() {
            const eligible = parseFloat(eligibleInput.value) || 0;
            const deductibleApplied = Math.min(eligible, deductibleLimit);
            const afterDeductible = Math.max(0, eligible - deductibleApplied);
            const copayAmount = afterDeductible * (copayPercent / 100);
            const finalPayout = Math.max(0, afterDeductible - copayAmount);

            if (previewDeductible) {
                previewDeductible.textContent = '₹ ' + deductibleApplied.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            }
            if (previewCopay) {
                previewCopay.textContent = '₹ ' + copayAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            }
            previewPayout.textContent = '₹ ' + finalPayout.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }

        eligibleInput.addEventListener('input', updatePayoutPreview);
        updatePayoutPreview();
    }
});
