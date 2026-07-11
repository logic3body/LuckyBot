"""
QR 码登录工具。

一行命令完成扫码登录，无需手动复制 Cookie。
自动保存完整凭证（含 ac_time_value），后续自动刷新无需再次登录。

青龙等无头环境：
    复制打印的链接到本地浏览器打开 → 手机扫码 → 脚本自动完成

用法:
    python login_qrcode.py
"""

import asyncio
import json
import os

from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents

QR_CODE_FILE = "qrcode.png"


def _get_qr_url(qr: QrCodeLogin) -> str:
    """获取登录二维码的 URL（浏览器打开后可扫码）"""
    try:
        return qr._QrCodeLogin__qr_link
    except AttributeError:
        return ""


async def main():
    print("正在获取二维码...")
    qr = QrCodeLogin()
    await qr.generate_qrcode()

    # 保存二维码图片
    pic = qr.get_qrcode_picture()
    pic.to_file(QR_CODE_FILE)
    print(f"二维码图片: {os.path.abspath(QR_CODE_FILE)}")

    # 登录链接（浏览器打开→手机扫码 或 直接用 B 站 App 扫码）
    url = _get_qr_url(qr)
    if url:
        print(f"登录链接: {url}")
        print("  浏览器打开链接 → 显示二维码 → 手机 App 扫码\n")
    else:
        print("")

    # 轮询扫码状态
    last_event = None
    while True:
        await asyncio.sleep(1.5)
        status = await qr.check_state()

        if status == QrCodeLoginEvents.DONE:
            print("\n✅ 登录成功！")
            break
        elif status == QrCodeLoginEvents.TIMEOUT:
            print("二维码已过期，重新生成...")
            await qr.generate_qrcode()
            pic = qr.get_qrcode_picture()
            pic.to_file(QR_CODE_FILE)
            url = _get_qr_url(qr)
            if url:
                print(f"新链接: {url}")
        elif status == QrCodeLoginEvents.CONF:
            if last_event != "CONF":
                print("已扫码，请在手机上确认登录...")
        elif status == QrCodeLoginEvents.SCAN:
            if last_event != "SCAN":
                print("等待扫码...")
        last_event = status.name if hasattr(status, 'name') else str(status)

    cred = qr.get_credential()
    data = {
        "sessdata": cred.sessdata,
        "bili_jct": cred.bili_jct,
        "buvid3": cred.buvid3,
        "buvid4": getattr(cred, "buvid4", ""),
        "dedeuserid": getattr(cred, "dedeuserid", ""),
        "ac_time_value": cred.ac_time_value,
    }

    with open("credential.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"   凭证已保存到 credential.json")
    print(f"   后续自动刷新，无需再次登录")


if __name__ == "__main__":
    asyncio.run(main())
