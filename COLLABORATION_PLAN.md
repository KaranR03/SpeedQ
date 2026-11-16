# Shared ownership and live intake

The next increment builds on the officer workspace already merged into main. It addresses two concrete gaps:
officers need reliable ownership when they work at the same time, and the handoff should be visible while a customer
card is being assembled.

## The plan and resulting flow

1. **Shared ownership:** claim a case, see who owns it, release it with a handoff note, and record who completed it.
   The server reserves claims under the existing store lock. A second officer can inspect a claimed case but cannot
   decide, complete, release or re-rank it. The current website sends a case revision with each mutation so an old
   approval cannot overwrite a newer customer correction or handoff.
2. **A case taking shape:** show unranked drafts separately from confirmed cases. The customer demo publishes the
   need, matched transaction, reported protection and conversation cues as those details are collected. Account
   signals are derived by the backend, not supplied as assertions by the client. No priority or executable plan is
   produced for a draft. Only explicit customer confirmation submits it to Prorio and the shared queue.
3. **Live handoff:** update the two officer sessions and their queue counts through a same-origin event stream.
   Confirmed intake cards show whether a case is queued, assigned or completed, and the customer status card names
   the assigned/completing officer. The existing activity trail keeps claims, releases and decisions attributable.

## Try it

- Open the officer workspace in two tabs. In local demo mode choose **Demo: Alex Morgan** in one tab and
  **Demo: Taylor Lee** in the other. This selector is explicitly a local simulation, not authentication.
- Review a sample case as Alex. Taylor sees Alex's ownership immediately and can inspect the case without acting on
  it. Complete it as Alex; Taylor's queue, completion count and detail view update without a reload.
- Claim another case, choose **Release case**, and let the other officer take over. Manual cases retain their manual
  workflow and notes through release and re-claim.
- Open `/demo`, start a customer scene and watch the officer pane switch to **Live intake**. Facts appear as the
  conversation progresses. After customer confirmation, the same handoff points to its ranked case.

## Identity and transport

Local demo identity is held per tab and sent in a header accepted only while staff authentication is disabled. For
distinct authenticated officers, `NRY_STAFF_ACCOUNTS` accepts a securely supplied JSON username/password mapping.
The account authenticated by the server determines ownership and audit identity; body names and demo headers cannot
impersonate another account. Existing `NRY_STAFF_USER` / `NRY_STAFF_PASSWORD` configuration remains available when a
mapping is not configured. A malformed mapping fails closed.

The event stream sends only an invalidation revision. Clients fetch authenticated snapshots to obtain case and draft
data. Reconnection requests a fresh snapshot; if streaming fails, a two-second backup refresh keeps the workspace
usable. Connected clients refresh age-based displays every ten seconds. Open decision dialogs are invalidated when
their case changes, while typed form fields are preserved until the user closes the dialog.

## Persistence and limits

Claims and revisions are persisted in the existing case documents; drafts are separate SQLite documents. Older case
records acquire safe defaults, with existing recorded pickup/decision identities used when restoring ownership.
Confirmation retries reuse the submitted case. The case also records an internal draft association so interrupted
submission can recover without duplicating a case, even if an officer has already completed it.

This remains a **single-backend-worker prototype**. The lock and event counter are process-local. Multiple production
workers need transactional database coordination and a shared event transport. Named Basic accounts are not SSO,
MFA, role separation or a production customer login. Use HTTPS for remote access. A live Retell agent must explicitly
call the draft API to stream its progress; the existing final-card webhook still works independently. The supplied
text conversations remain scripted, with real backend updates rather than a newly integrated language model.

## Verification and delivery

Tests cover simultaneous claims, independent completions, ownership transfers, stale approvals, identity spoofing,
draft ownership checks, confirmation retries, cancellation and restart recovery. Browser checks use two independent
sessions and the actual customer demo, plus desktop/mobile screenshots and automated accessibility checks.

Delivery is a feature branch and a pull request targeting **main**. The user retains the final merge confirmation in
GitHub. Environment publication and a branch push do not establish that the pull request has been merged.
