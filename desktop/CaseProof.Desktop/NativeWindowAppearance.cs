using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;

namespace CaseProof.Desktop;

internal static class NativeWindowAppearance
{
    private const int CornerPreference = 33;
    private const int BorderColor = 34;
    private const int CaptionColor = 35;
    private const int TextColor = 36;
    private const uint SystemColor = 0xFFFFFFFF;

    internal static void Apply(Window window)
    {
        if (!OperatingSystem.IsWindowsVersionAtLeast(10, 0, 22000)) return;
        var handle = new WindowInteropHelper(window).Handle;
        if (handle == 0) return;

        var highContrast = SystemParameters.HighContrast;
        Set(handle, CaptionColor, highContrast ? SystemColor : ColorRef(0x08, 0x08, 0x08));
        Set(handle, TextColor, highContrast ? SystemColor : ColorRef(0xF1, 0xF1, 0xF1));
        Set(handle, BorderColor, highContrast ? SystemColor : ColorRef(0x34, 0x34, 0x34));
        Set(handle, CornerPreference, highContrast ? 0u : 2u);
    }

    private static uint ColorRef(byte red, byte green, byte blue) => (uint)(red | green << 8 | blue << 16);

    private static void Set(nint handle, int attribute, uint value) =>
        _ = DwmSetWindowAttribute(handle, attribute, ref value, sizeof(uint));

    [DllImport("dwmapi.dll", ExactSpelling = true)]
    private static extern int DwmSetWindowAttribute(nint window, int attribute, ref uint value, uint size);
}
