import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

class SpinaDesignPreviewPage extends StatefulWidget {
  const SpinaDesignPreviewPage({super.key});

  @override
  State<SpinaDesignPreviewPage> createState() => _SpinaDesignPreviewPageState();
}

class _SpinaDesignPreviewPageState extends State<SpinaDesignPreviewPage> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('spina-design-preview'),
      appBar: AppBar(
        title: const Text('SPINA UI Review'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(
              child: Chip(
                avatar: const Icon(Icons.phone_android_rounded, size: 18),
                label: const Text('Android CA1'),
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
          children: [
            _HeroCard(onShowConfirmation: () => _showConfirmation(context)),
            const SizedBox(height: 16),
            const _SectionTitle(
              title: 'Core components',
              subtitle: 'Shared visual language for every SPINA role.',
            ),
            const SizedBox(height: 10),
            LayoutBuilder(
              builder: (context, constraints) {
                final twoColumns = constraints.maxWidth >= 560;
                final width = twoColumns
                    ? (constraints.maxWidth - 12) / 2
                    : constraints.maxWidth;
                return Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    SizedBox(width: width, child: const _ActionCard()),
                    SizedBox(width: width, child: const _StatusCard()),
                  ],
                );
              },
            ),
            const SizedBox(height: 20),
            const _SectionTitle(
              title: 'Form language',
              subtitle: 'Clear labels, comfortable touch targets and simple wording.',
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  children: [
                    const TextField(
                      decoration: InputDecoration(
                        labelText: 'Client name',
                        hintText: 'Search or enter a name',
                        prefixIcon: Icon(Icons.person_outline_rounded),
                      ),
                    ),
                    const SizedBox(height: 12),
                    const TextField(
                      decoration: InputDecoration(
                        labelText: 'Amount',
                        hintText: '0.00',
                        prefixIcon: Icon(Icons.payments_outlined),
                      ),
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 14),
                    FilledButton.icon(
                      onPressed: () {},
                      icon: const Icon(Icons.check_rounded),
                      label: const Text('Continue'),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),
            const _SectionTitle(
              title: 'User states',
              subtitle: 'The next action should always be obvious.',
            ),
            const SizedBox(height: 10),
            const _StateCard(
              icon: Icons.wifi_off_rounded,
              title: 'You are offline',
              message:
                  'You can review available information, but financial actions need an internet connection.',
              action: 'Try again',
            ),
            const SizedBox(height: 10),
            const _StateCard(
              icon: Icons.lock_outline_rounded,
              title: 'Access unavailable',
              message:
                  'Your current permissions do not allow this action. Your account and notifications are still available.',
              action: 'Go back',
            ),
            const SizedBox(height: 20),
            const _SectionTitle(
              title: 'Role language',
              subtitle: 'Same theme, different priorities.',
            ),
            const SizedBox(height: 10),
            const _RoleStrip(),
          ],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (value) => setState(() => _selectedIndex = value),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home_rounded),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.notifications_outlined),
            selectedIcon: Icon(Icons.notifications_rounded),
            label: 'Alerts',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline_rounded),
            selectedIcon: Icon(Icons.person_rounded),
            label: 'Account',
          ),
        ],
      ),
    );
  }

  Future<void> _showConfirmation(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Confirm before continuing',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Financial actions will always explain the amount, source and result before you confirm.',
                ),
                const SizedBox(height: 18),
                FilledButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('I understand'),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Cancel'),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _HeroCard extends StatelessWidget {
  const _HeroCard({required this.onShowConfirmation});

  final VoidCallback onShowConfirmation;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFF7FA), Color(0xFFFFE7F1)],
        ),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: const Color(0xFFF1D6E1)),
      ),
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
            ),
            alignment: Alignment.center,
            child: const Text(
              'S',
              style: TextStyle(
                color: SpinaTheme.brandPinkDark,
                fontWeight: FontWeight.w900,
                fontSize: 24,
              ),
            ),
          ),
          const SizedBox(height: 18),
          Text('Independent. Clear. SPINA.',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          const Text(
            'Pink and white with confident contrast, calm spacing and clear actions. Feminine without feeling fragile.',
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              FilledButton.icon(
                onPressed: onShowConfirmation,
                icon: const Icon(Icons.visibility_outlined),
                label: const Text('Review confirmation'),
              ),
              OutlinedButton.icon(
                onPressed: () {},
                icon: const Icon(Icons.tune_rounded),
                label: const Text('Secondary action'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title, required this.subtitle});

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 3),
        Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

class _ActionCard extends StatelessWidget {
  const _ActionCard();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(Icons.touch_app_outlined, color: SpinaTheme.brandPinkDark),
            const SizedBox(height: 12),
            Text('Easy actions', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 5),
            const Text('One obvious primary action, with secondary choices visually quieter.'),
            const SizedBox(height: 16),
            FilledButton(onPressed: () {}, child: const Text('Primary action')),
            const SizedBox(height: 8),
            OutlinedButton(onPressed: () {}, child: const Text('Secondary action')),
          ],
        ),
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  const _StatusCard();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.label_important_outline_rounded,
                color: SpinaTheme.brandPinkDark),
            const SizedBox(height: 12),
            Text('Readable status', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 5),
            const Text('Status uses both words and restrained color so meaning never depends on pink alone.'),
            const SizedBox(height: 14),
            const Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                Chip(label: Text('Active')),
                Chip(label: Text('Pending review')),
                Chip(label: Text('Read only')),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _StateCard extends StatelessWidget {
  const _StateCard({
    required this.icon,
    required this.title,
    required this.message,
    required this.action,
  });

  final IconData icon;
  final String title;
  final String message;
  final String action;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: SpinaTheme.brandPinkSoft,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, color: SpinaTheme.brandPinkDark),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 4),
                  Text(message),
                  const SizedBox(height: 6),
                  TextButton(onPressed: () {}, child: Text(action)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RoleStrip extends StatelessWidget {
  const _RoleStrip();

  @override
  Widget build(BuildContext context) {
    const roles = <(IconData, String, String)>[
      (Icons.insights_outlined, 'Management', 'Overview & approvals'),
      (Icons.badge_outlined, 'Employee', 'Work & office tasks'),
      (Icons.route_outlined, 'Collector', 'Fast field collection'),
      (Icons.favorite_border_rounded, 'Client', 'Simple borrower view'),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            for (var index = 0; index < roles.length; index++) ...[
              ListTile(
                contentPadding: const EdgeInsets.symmetric(horizontal: 4),
                leading: Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: SpinaTheme.blush,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(roles[index].$1, color: SpinaTheme.brandPinkDark),
                ),
                title: Text(roles[index].$2),
                subtitle: Text(roles[index].$3),
                trailing: const Icon(Icons.chevron_right_rounded),
              ),
              if (index != roles.length - 1) const Divider(),
            ],
          ],
        ),
      ),
    );
  }
}
