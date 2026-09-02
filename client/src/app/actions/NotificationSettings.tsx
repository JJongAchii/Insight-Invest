"use client";

import { Bell, BellOff, Send } from "lucide-react";
import { useEffect, useState } from "react";

import {
  useFetchNotificationConfigQuery,
  useSendTestNotificationMutation,
  useSubscribeNotificationsMutation,
  useUnsubscribeNotificationsMutation,
} from "@/state/api";

const toUint8Array = (value: string) => {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  return Uint8Array.from([...raw].map((character) => character.charCodeAt(0)));
};

export default function NotificationSettings() {
  const { data: config, isLoading } = useFetchNotificationConfigQuery();
  const [subscribe, { isLoading: isSubscribing }] = useSubscribeNotificationsMutation();
  const [unsubscribe, { isLoading: isUnsubscribing }] = useUnsubscribeNotificationsMutation();
  const [sendTest, { isLoading: isTesting }] = useSendTestNotificationMutation();
  const [subscription, setSubscription] = useState<PushSubscription | null>(null);
  const [message, setMessage] = useState("");
  const [supported, setSupported] = useState(true);

  useEffect(() => {
    const available = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    setSupported(available);
    if (!available) return;
    navigator.serviceWorker.ready
      .then((registration) => registration.pushManager.getSubscription())
      .then(setSubscription)
      .catch(() => setMessage("현재 알림 구독 상태를 확인하지 못했습니다."));
  }, []);

  const enable = async () => {
    if (!config?.public_key) return;
    try {
      setMessage("");
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setMessage("알림 권한이 허용되지 않았습니다. iPhone 설정에서도 다시 변경할 수 있습니다.");
        return;
      }
      const registration = await navigator.serviceWorker.ready;
      const current =
        (await registration.pushManager.getSubscription()) ??
        (await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: toUint8Array(config.public_key),
        }));
      const json = current.toJSON();
      if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
        throw new Error("invalid subscription");
      }
      await subscribe({
        endpoint: json.endpoint,
        keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
        user_agent: navigator.userAgent,
      }).unwrap();
      setSubscription(current);
      setMessage("이 기기로 Action과 Research 업데이트를 알려드립니다.");
    } catch {
      setMessage("알림을 활성화하지 못했습니다. 홈 화면 앱에서 다시 시도해 주세요.");
    }
  };

  const disable = async () => {
    if (!subscription) return;
    try {
      await unsubscribe({ endpoint: subscription.endpoint }).unwrap();
      await subscription.unsubscribe();
      setSubscription(null);
      setMessage("이 기기의 알림을 해제했습니다.");
    } catch {
      setMessage("알림을 해제하지 못했습니다.");
    }
  };

  const test = async () => {
    try {
      const result = await sendTest().unwrap();
      if (result.sent > 0) {
        setMessage("테스트 알림을 전송했습니다.");
      } else if (result.subscriptions === 0) {
        setMessage("서버에 활성 구독이 없습니다. 이 기기의 알림을 다시 활성화해 주세요.");
      } else if (result.failed > 0) {
        setMessage("Push 제공자가 전송을 거절했습니다. 잠시 후 다시 시도해 주세요.");
      } else {
        setMessage("전송할 테스트 알림이 없습니다.");
      }
    } catch {
      setMessage("테스트 알림을 전송하지 못했습니다.");
    }
  };

  return (
    <section className="card">
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-primary-500/15 p-2 text-primary-400">
          {subscription ? <Bell size={20} /> : <BellOff size={20} />}
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-ink">Device Notifications</h2>
          <p className="mt-1 text-sm text-ink-secondary">
            중요한 Action과 새로운 Research Radar 자료를 이 기기로 전송합니다.
          </p>

          {!supported ? (
            <p className="mt-3 text-sm text-warning">이 브라우저는 Web Push를 지원하지 않습니다.</p>
          ) : isLoading ? (
            <p className="mt-3 text-sm text-ink-muted">알림 설정을 확인하는 중...</p>
          ) : !config?.enabled ? (
            <p className="mt-3 text-sm text-warning">
              서버 Push Key 설정이 완료되지 않아 아직 활성화할 수 없습니다.
            </p>
          ) : (
            <div className="mt-4 flex flex-wrap gap-2">
              {subscription ? (
                <>
                  <button type="button" className="btn-secondary inline-flex items-center gap-1.5" onClick={test} disabled={isTesting}>
                    <Send size={15} aria-hidden /> {isTesting ? "Sending..." : "Send Test"}
                  </button>
                  <button type="button" className="btn-secondary" onClick={disable} disabled={isUnsubscribing}>
                    {isUnsubscribing ? "Disabling..." : "Disable on This Device"}
                  </button>
                </>
              ) : (
                <button type="button" className="btn-primary inline-flex items-center gap-1.5" onClick={enable} disabled={isSubscribing}>
                  <Bell size={15} aria-hidden /> {isSubscribing ? "Enabling..." : "Enable Notifications"}
                </button>
              )}
            </div>
          )}
          {message && <p className="mt-3 text-sm text-ink-secondary">{message}</p>}
          <p className="mt-3 text-xs text-ink-muted">
            iPhone에서는 Safari에서 홈 화면에 추가한 Insight Invest 앱을 열고 활성화해야 합니다.
          </p>
        </div>
      </div>
    </section>
  );
}
