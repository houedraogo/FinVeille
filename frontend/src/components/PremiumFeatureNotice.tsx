"use client";

import LimitNotice, { PREMIUM_FEATURE_MESSAGE } from "@/components/LimitNotice";

interface PremiumFeatureNoticeProps {
  title?: string;
  message?: string;
  compact?: boolean;
}

export { PREMIUM_FEATURE_MESSAGE };

export default function PremiumFeatureNotice({
  title = "Fonctionnalité premium",
  message = PREMIUM_FEATURE_MESSAGE,
  compact = false,
}: PremiumFeatureNoticeProps) {
  return <LimitNotice title={title} message={message} compact={compact} />;
}
