import 'package:flutter/widgets.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/office/office_operation.dart';

/// One non-idempotent intake-create lifetime inside the authorized app shell.
/// Ordinary route navigation and compatible token refresh cannot discard it.
class OfficeIntakeAuthorityHost extends StatefulWidget {
  const OfficeIntakeAuthorityHost({
    required this.session,
    required this.child,
    super.key,
  });
  final UserSession? session;
  final Widget child;
  @override
  State<OfficeIntakeAuthorityHost> createState() =>
      _OfficeIntakeAuthorityHostState();
}

class _OfficeIntakeAuthorityHostState extends State<OfficeIntakeAuthorityHost> {
  late OfficeOperation _operation = OfficeOperation()
    ..denied = widget.session == null;
  @override
  void didUpdateWidget(OfficeIntakeAuthorityHost oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session?.authorizationScopeKey !=
        widget.session?.authorizationScopeKey) {
      _operation.dispose();
      _operation = OfficeOperation()..denied = widget.session == null;
    }
  }

  @override
  void dispose() {
    _operation.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => OfficeIntakeAuthority(
    authorizationScopeKey: widget.session?.authorizationScopeKey,
    operation: _operation,
    child: widget.child,
  );
}

class OfficeIntakeAuthority extends InheritedWidget {
  const OfficeIntakeAuthority({
    required this.authorizationScopeKey,
    required this.operation,
    required super.child,
    super.key,
  });
  final String? authorizationScopeKey;
  final OfficeOperation operation;
  static OfficeIntakeAuthority? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<OfficeIntakeAuthority>();
  @override
  bool updateShouldNotify(OfficeIntakeAuthority oldWidget) =>
      operation != oldWidget.operation;
}
