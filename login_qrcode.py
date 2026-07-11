"""
QR 码登录工具。

一行命令完成扫码登录，无需手动复制 Cookie。
自动保存完整凭证（含 ac_time_value），后续自动刷新无需再次登录。

用法:
    python login_qrcode.py
"""

import asyncio
import json
import os

from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents

QR_CODE_FILE = "qrcode.png"


async def main():
    print("正在获取二维码...")
    qr = QrCodeLogin()
    await qr.generate_qrcode()

    # 保存二维码图片
    pic = qr.get_qrcode_picture()
    pic.save(QR_CODE_FILE)
    print(f"二维码已保存: {os.path.abspath(QR_CODE_FILE)}")

    # 同时在终端显示
    term = qr.get_qrcode_terminal()
    if term:
        print(term)

    print("用手机 B 站 App 扫码登录\n")

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
            pic.save(QR_CODE_FILE)
            term = qr.get_qrcode_terminal()
            if term:
                print(term)
        elif status == QrCodeLoginEvents.CONF:
            if last_event != "CONF":
                print("请在手机上确认登录...")
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
    print(f"   预设有效期约 30 天，程序会在过期前自动刷新")


if __name__ == "__main__":
    asyncio.run(main())
