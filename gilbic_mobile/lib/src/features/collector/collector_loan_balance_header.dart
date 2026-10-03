import 'package:flutter/material.dart';

/// Keeps a loan label and its supplied display balance readable at OS scale.
class CollectorLoanBalanceHeader extends StatelessWidget {
  const CollectorLoanBalanceHeader({
    required this.label,
    required this.balance,
    required this.labelStyle,
    required this.balanceStyle,
    super.key,
  });

  final String label;
  final String balance;
  final TextStyle? labelStyle;
  final TextStyle? balanceStyle;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final measured = TextPainter(
        text: TextSpan(
          children: [
            TextSpan(text: label, style: labelStyle),
            TextSpan(text: balance, style: balanceStyle),
          ],
        ),
        textDirection: Directionality.of(context),
        textScaler: MediaQuery.textScalerOf(context),
      )..layout();
      final stacked = measured.width > constraints.maxWidth;
      measured.dispose();
      final loanLabel = Text(label, style: labelStyle);
      final fullBalance = Text(balance, style: balanceStyle);
      if (stacked) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [loanLabel, fullBalance],
        );
      }
      return Row(
        children: [
          Expanded(child: loanLabel),
          fullBalance,
        ],
      );
    },
  );
}
