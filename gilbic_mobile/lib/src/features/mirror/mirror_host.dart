import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_controller.dart';
import 'package:gilbic_mobile/src/features/mirror/safe_mirror_surface.dart';

/// Controls are intentionally outside every captured subtree.
class MirrorHost extends StatelessWidget {
  const MirrorHost({
    required this.controller,
    required this.onOpenViewer,
    required this.child,
    super.key,
  });
  final MirrorController controller;
  final VoidCallback onOpenViewer;
  final Widget child;
  @override
  Widget build(BuildContext context) => MirrorScope(
    controller: controller,
    child: AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final grant = controller.sharing;
        final pending = controller.incoming.isEmpty
            ? null
            : controller.incoming.first;
        return Column(
          children: [
            if (grant != null || pending != null || controller.mayView)
              Material(
                color: Theme.of(context).colorScheme.surfaceContainer,
                child: SafeArea(
                  bottom: false,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 4,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (grant != null)
                          Wrap(
                            crossAxisAlignment: WrapCrossAlignment.center,
                            spacing: 12,
                            children: [
                              Text(
                                controller.viewing
                                    ? 'Viewing ${grant.holderName} — ${grant.state}'
                                    : 'Sharing Spina with ${grant.viewerName}',
                              ),
                              TextButton(
                                onPressed: controller.stop,
                                child: const Text('Stop sharing'),
                              ),
                            ],
                          )
                        else if (pending != null) ...[
                          Text(
                            '${pending.viewerName} requests to view your Spina screen. No control or recording. Sensitive screens are excluded.',
                          ),
                          Wrap(
                            spacing: 12,
                            children: [
                              TextButton(
                                onPressed: controller.canAccept
                                    ? () => controller.accept(pending)
                                    : null,
                                child: const Text('Allow viewing'),
                              ),
                              TextButton(
                                onPressed: () => controller.decline(pending),
                                child: const Text('Decline'),
                              ),
                            ],
                          ),
                          if (!controller.canAccept)
                            const Text(
                              'Open a supported daily-work screen to allow viewing.',
                            ),
                        ] else if (controller.mayView)
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton.icon(
                              onPressed: onOpenViewer,
                              icon: const Icon(Icons.screen_share_outlined),
                              label: const Text('Request screen view'),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            Expanded(child: child),
          ],
        );
      },
    ),
  );
}
