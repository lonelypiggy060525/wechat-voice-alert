import asyncio
from winsdk.windows.ui.notifications.management import UserNotificationListener, UserNotificationListenerAccessStatus
from winsdk.windows.ui.notifications import NotificationKinds, KnownNotificationBindings


async def main():
    listener = UserNotificationListener.current
    st = listener.get_access_status()
    print("access status:", st)
    if st != UserNotificationListenerAccessStatus.ALLOWED:
        print("requesting access...")
        st = await listener.request_access_async()
        print("after request:", st)
    notifs = await listener.get_notifications_async(NotificationKinds.TOAST)
    print("existing toasts:", len(notifs))
    for n in notifs:
        try:
            app = n.app_info.display_info.display_name
            aumid = n.app_info.app_user_model_id
        except Exception as e:
            app, aumid = f"<err {e}>", "?"
        texts = []
        try:
            binding = n.notification.visual.get_binding(KnownNotificationBindings.TOAST_GENERIC)
            if binding:
                texts = [t.text for t in binding.get_text_elements()]
        except Exception as e:
            texts = [f"<err {e}>"]
        print(f"- app={app!r} aumid={aumid!r} id={n.id} created={n.creation_time} texts={texts}")


asyncio.run(main())
