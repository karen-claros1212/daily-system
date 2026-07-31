// ─── Daily Offline Status ──────────────────────────────────────────
// Discrete offline status indicator.

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

enum OfflineStatus {
  savedLocal(label: 'Guardado en este teléfono', icon: Icons.save),
  pendingSync(label: 'Pendiente de sincronizar', icon: Icons.cloud_queue),
  synced(label: 'Todo sincronizado', icon: Icons.cloud_done);

  final String label;
  final IconData icon;
  const OfflineStatus({required this.label, required this.icon});
}

class DailyOfflineStatus extends StatelessWidget {
  final OfflineStatus status;

  const DailyOfflineStatus({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: status.label,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            status.icon,
            size: 14,
            color: status == OfflineStatus.synced
                ? DailyTokens.accent
                : status == OfflineStatus.pendingSync
                    ? DailyTokens.warning
                    : DailyTokens.outlineVariant,
          ),
          const SizedBox(width: 4),
          Text(
            status.label,
            style: const TextStyle(fontSize: 11, color: DailyTokens.outlineVariant),
          ),
        ],
      ),
    );
  }
}
