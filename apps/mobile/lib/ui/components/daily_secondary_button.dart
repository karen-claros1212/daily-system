// ─── Daily Secondary Button ────────────────────────────────────────

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

class DailySecondaryButton extends StatelessWidget {
  final String label;
  final VoidCallback onPressed;
  final IconData? icon;
  final bool isLoading;

  const DailySecondaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: DailyTokens.spacingXXL,
      child: OutlinedButton.icon(
        onPressed: isLoading ? null : onPressed,
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          side: const BorderSide(color: DailyTokens.outline, width: 1),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(DailyTokens.shapeMD),
          ),
          textStyle: const TextStyle(
            fontSize: 14, fontWeight: FontWeight.w600, letterSpacing: 0.5,
          ),
        ),
        icon: isLoading
            ? SizedBox(width: 20, height: 20,
                child: CircularProgressIndicator(strokeWidth: 2))
            : (icon != null ? Icon(icon, size: 20) : const SizedBox()),
        label: Text(label),
      ),
    );
  }
}
