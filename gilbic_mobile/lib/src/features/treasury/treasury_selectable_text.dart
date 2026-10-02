import 'package:flutter/material.dart';

/// Readable server facts support selection without editable-field semantics.
class TreasurySelectableText extends StatelessWidget {
  const TreasurySelectableText(this.data, {super.key});
  final String data;
  @override
  Widget build(BuildContext context) => SelectionArea(child: Text(data));
}
