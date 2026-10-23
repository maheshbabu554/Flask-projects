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

    // Hospital desk policy/member text search backed by the Flask endpoint.
    const hospitalSearch = document.getElementById('hospital_policy_search');
    const policyHidden = document.getElementById('policy_select');
    const policyResults = document.getElementById('hospital_policy_results');
    const memberHidden = document.getElementById('member_select');
    const memberText = document.getElementById('selected_member_text');
    const policySummary = document.getElementById('selected_policy_summary');
    if (hospitalSearch && policyHidden && policyResults && memberHidden && memberText) {
        let timer;
        const clearSelection = () => {
            policyHidden.value = '';
            memberHidden.value = '';
            memberText.value = '';
            if (policySummary) policySummary.textContent = '';
        };
        hospitalSearch.addEventListener('input', () => {
            clearSelection();
            policyResults.replaceChildren();
            const query = hospitalSearch.value.trim();
            if (!query) return;
            window.clearTimeout(timer);
            timer = window.setTimeout(async () => {
                try {
                    const response = await fetch(`/api/hospital/policy-search?q=${encodeURIComponent(query)}`, {headers: {'Accept': 'application/json'}});
                    if (!response.ok) throw new Error('Search failed');
                    const data = await response.json();
                    if (!data.results.length) {
                        const empty = document.createElement('div');
                        empty.className = 'list-group-item small text-muted';
                        empty.textContent = 'No matching active policy or covered member found.';
                        policyResults.appendChild(empty);
                        return;
                    }
                    data.results.forEach(policy => {
                        const card = document.createElement('div');
                        card.className = 'list-group-item';
                        const title = document.createElement('div');
                        title.className = 'fw-semibold';
                        title.textContent = `Policy #${policy.policy_id} — ${policy.plan_name}`;
                        const info = document.createElement('div');
                        info.className = 'small text-muted';
                        info.textContent = `Holder: ${policy.holder_name} | Valid ${policy.start_date} to ${policy.end_date} | Remaining cover ₹${Number(policy.remaining_cover).toLocaleString('en-IN')}`;
                        card.append(title, info);
                        (policy.members || []).forEach(member => {
                            const button = document.createElement('button');
                            button.type = 'button';
                            button.className = 'btn btn-sm btn-outline-primary mt-2 me-2';
                            button.textContent = `Select ${member.display_name} (${member.relationship})`;
                            button.addEventListener('click', () => {
                                policyHidden.value = policy.policy_id;
                                memberHidden.value = member.member_id;
                                memberText.value = `${member.display_name} (${member.relationship})`;
                                hospitalSearch.value = `Policy #${policy.policy_id} — ${policy.holder_name}`;
                                if (policySummary) policySummary.textContent = `Selected ${policy.plan_name}; remaining cover ₹${Number(policy.remaining_cover).toLocaleString('en-IN')}.`;
                                policyResults.replaceChildren();
                            });
                            card.appendChild(button);
                        });
                        policyResults.appendChild(card);
                    });
                } catch (error) {
                    policyResults.textContent = 'Policy search failed. Please try again.';
                }
            }, 200);
        });
    }
});
