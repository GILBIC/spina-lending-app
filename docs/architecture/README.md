# SPINA architecture hub

Use the [29 September implementation state](../release/2026-09-29-implementation-state.md) for audit fixes, configuration and acceptance. The [whole-system map](system-map.md) identifies code owners; the [debugging playbook](debugging-playbook.md) follows an action from interface to authoritative record.

The original standalone Tkinter desktop and its generated source maps are retired. Windows now refers to the shared company portal installed by `spina_pc/`. Historical wave/progress documents describe the old implementation and remain historical evidence only; they are not current run or deployment instructions.

## Source and evidence

Use merged source, numbered database migrations and protected regression tests to establish implementation. Use exact-revision CI and deployment records for delivery. Keep actual company/provider/device acceptance distinct from synthetic tests. [Issue 296](https://github.com/GILBIC/spina-lending-app/issues/296) preserves the roadmap and [issue 448](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5872009447) tracks all remaining priorities.

Update this map when a change affects an API/data owner, financial rule, permission, device/session boundary, offline or retry behavior, supported surface or release gate. An open branch is in progress; a successful build is not evidence of production deployment or final acceptance.
