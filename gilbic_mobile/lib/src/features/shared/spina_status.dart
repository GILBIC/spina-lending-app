import 'package:flutter/material.dart';

/// Presentation only: callers retain authority over the domain state.
enum SpinaStatusTone { success, attention, blocked, information }

class SpinaStatusLabel extends StatelessWidget {
  const SpinaStatusLabel({required this.label, required this.tone, this.icon,
    this.semanticLabel, super.key});
  final String label;
  final SpinaStatusTone tone;
  final IconData? icon;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final (background, foreground, defaultIcon) = switch (tone) {
      SpinaStatusTone.success => (colors.secondaryContainer, colors.onSecondaryContainer, Icons.check_circle_outline),
      SpinaStatusTone.attention => (colors.tertiaryContainer, colors.onTertiaryContainer, Icons.pending_outlined),
      SpinaStatusTone.blocked => (colors.errorContainer, colors.onErrorContainer, Icons.block_outlined),
      SpinaStatusTone.information => (colors.surfaceContainerHighest, colors.onSurface, Icons.info_outline),
    };
    return Semantics(label: semanticLabel ?? label, child: ExcludeSemantics(
      child: Container(padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
        decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(12)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon ?? defaultIcon, size: 16, color: foreground),
          const SizedBox(width: 4),
          Flexible(child: Text(label, style: Theme.of(context).textTheme.labelMedium?.copyWith(color: foreground))),
        ]),
      ),
    ));
  }
}
