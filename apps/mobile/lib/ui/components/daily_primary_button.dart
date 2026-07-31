// ─── Daily Primary Button ─────────────────────────────────────────

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

class DailyPrimaryButton extends StatelessWidget {
  final String label;
  final VoidCallback onPressed;
  final IconData? icon;
  final bool isLoading;
  final Color? color;
  final double? width;

  const DailyPrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.isLoading = false,
    this.color,
    this.width,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width ?? double.infinity,
      height: DailyTokens.spacingXXL,
      child: FilledButton.icon(
        onPressed: isLoading ? null : onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: color ?? DailyTokens.primary,
          foregroundColor: DailyTokens.onPrimary,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(DailyTokens.shapeMD),
          ),
          elevation: 0,
          textStyle: const TextStyle(
            fontSize: 15, fontWeight: FontWeight.w600, letterSpacing: 0.5,
          ),
        ),
        icon: isLoading
            ? SizedBox(
                width: 20, height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: DailyTokens.onPrimary,
                ),
              )
            : (icon != null ? Icon(icon, size: 20) : const SizedBox()),
        label: Text(label),
      ),
    );
  }
}
