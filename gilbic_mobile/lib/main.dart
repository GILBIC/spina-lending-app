import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/features/collector/collector_synthetic_review_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  if (kDebugMode) {
    runApp(
      MaterialApp(
        title: 'SPINA Collector CA4 Review',
        debugShowCheckedModeBanner: false,
        theme: SpinaTheme.light,
        home: const CollectorSyntheticReviewPage(),
      ),
    );
    return;
  }
  runApp(const GilbicApp());
}
