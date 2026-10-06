import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_application_page.dart';
import 'package:gilbic_mobile/src/features/office/office_first_loan_page.dart';
import 'package:gilbic_mobile/src/features/office/office_intake_page.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';

/// Private, paginated choices. Selecting a row only opens a protected read.
class OfficeFinderPage extends StatefulWidget {
  const OfficeFinderPage({
    required this.actor,
    required this.repository,
    this.intakeReference,
    this.clientId,
    super.key,
  });
  final OfficeIdentity actor;
  final OfficeRepository repository;
  final String? intakeReference;
  final String? clientId;
  @override
  State<OfficeFinderPage> createState() => _OfficeFinderPageState();
}

class _OfficeFinderPageState extends OfficeScreenState<OfficeFinderPage> {
  final fields = OfficeFields();
  OfficeRecord? page;
  String query = '', status = '', selectedStatus = '';
  String? cursor;
  List<String?> history = [];
  bool get applications => widget.clientId != null;
  @override
  void initState() {
    super.initState();
    _read();
  }

  @override
  void clearPrivate() {
    fields.clear();
    page = null;
    history = [];
    cursor = null;
    query = '';
    status = '';
    selectedStatus = '';
  }

  @override
  void dispose() {
    fields.dispose();
    super.dispose();
  }

  Future<void> _read({String? at, List<String?> previous = const []}) async {
    final value = await operation.run(
      () => applications
          ? widget.repository.findApplications(
              widget.actor,
              widget.intakeReference!,
              widget.clientId!,
              cursor: at,
            )
          : widget.repository.findIntakes(
              widget.actor,
              query: query,
              status: status,
              cursor: at,
            ),
      reconcile: true,
    );
    if (mounted && value != null) {
      setState(() {
        page = value;
        cursor = at;
        history = previous;
      });
    }
  }

  Future<void> _open(Widget child) async {
    await Navigator.of(
      context,
    ).push<void>(MaterialPageRoute(builder: (_) => child));
    if (!mounted) return;
    if (widget.actor.accessDenied) {
      denyAccess();
    } else {
      await _read(at: cursor, previous: history);
    }
  }

  void _search() {
    setState(() {
      query = fields.text('search');
      status = selectedStatus;
      page = null;
      history = [];
      cursor = null;
    });
    _read();
  }

  @override
  Widget build(BuildContext context) {
    final items = page == null
        ? <OfficeRecord>[]
        : officeRecords(page!['items']);
    return screen(
      applications ? 'Applications for this client' : 'Recent office intakes',
      [
        if (applications) ...[
          Text('Intake: ${widget.intakeReference}'),
          officeButton(
            'New application',
            operation.busy
                ? null
                : () => _open(
                    OfficeApplicationPage(
                      actor: widget.actor,
                      repository: widget.repository,
                      clientId: widget.clientId!,
                      startNew: true,
                    ),
                  ),
            primary: true,
          ),
        ] else ...[
          const Text(
            'Find a saved intake by name, phone, intake or application reference.',
          ),
          const SizedBox(height: 12),
          officeField(
            fields,
            'search',
            'Find an intake or application',
            enabled: !operation.busy,
            maxLength: 200,
          ),
          DropdownButtonFormField<String>(
            initialValue: selectedStatus,
            isExpanded: true,
            decoration: const InputDecoration(labelText: 'Intake status'),
            items: [
              const DropdownMenuItem(
                value: '',
                child: Text('All intake statuses'),
              ),
              for (final entry in officeIntakeStatuses.entries)
                DropdownMenuItem(value: entry.key, child: Text(entry.value)),
            ],
            onChanged: operation.busy
                ? null
                : (value) => setState(() => selectedStatus = value ?? ''),
          ),
          const SizedBox(height: 12),
          officeButton(
            'Search',
            operation.busy ? null : _search,
            primary: true,
          ),
        ],
        if (page != null && items.isEmpty)
          Text(
            applications
                ? 'No saved applications for this client.'
                : 'No matching office intakes.',
          ),
        for (final item in items)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    applications
                        ? item['application_reference']
                        : item['full_name'],
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  if (applications) ...[
                    Text(
                      item['version_number'] == null
                          ? 'No saved version'
                          : 'Saved version ${item['version_number']}',
                    ),
                    officeButton(
                      'Open ${item['application_reference']}',
                      operation.busy
                          ? null
                          : () => _open(
                              OfficeApplicationPage(
                                actor: widget.actor,
                                repository: widget.repository,
                                clientId: widget.clientId!,
                                applicationReference:
                                    item['application_reference'],
                              ),
                            ),
                    ),
                    officeButton(
                      'First-loan review and release',
                      operation.busy || item['application_version_id'] == null
                          ? null
                          : () => _open(
                              OfficeFirstLoanPage(
                                actor: widget.actor,
                                repository: widget.repository,
                                clientId: widget.clientId!,
                                applicationReference:
                                    item['application_reference'],
                              ),
                            ),
                    ),
                  ] else ...[
                    Text('Phone: ${item['phone_number']}'),
                    Text(officeIntakeStatuses[item['intake_status']]!),
                    officeButton(
                      'Continue ${item['intake_reference']}',
                      operation.busy
                          ? null
                          : () => _open(
                              OfficeIntakePage(
                                actor: widget.actor,
                                repository: widget.repository,
                                reference: item['intake_reference'],
                              ),
                            ),
                      primary: true,
                    ),
                  ],
                ],
              ),
            ),
          ),
        if (history.isNotEmpty)
          officeButton(
            'Previous page',
            operation.busy
                ? null
                : () => _read(
                    at: history.last,
                    previous: history.sublist(0, history.length - 1),
                  ),
          ),
        if (page?['has_more'] == true)
          officeButton(
            'Next page',
            operation.busy
                ? null
                : () => _read(
                    at: page!['next_cursor'],
                    previous: [...history, cursor],
                  ),
          ),
      ],
      reload: () => _read(at: cursor, previous: history),
    );
  }
}
