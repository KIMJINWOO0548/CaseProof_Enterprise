using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Media;

namespace CaseProof.Desktop;

public partial class MainWindow
{
    private bool Prompt(string title, string introduction, string command, string automationId,
        IReadOnlyList<(string Label, Control Input)> fields, Func<string?> validate)
    {
        var dialog = new Window
        {
            Title = title, Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Width = Math.Min(560, Math.Max(390, ActualWidth - 75)), MaxHeight = Math.Max(420, ActualHeight - 44),
            SizeToContent = SizeToContent.Height, ResizeMode = ResizeMode.NoResize, ShowInTaskbar = false,
            FontFamily = FontFamily, FontSize = 14, Background = Brushes.White
        };
        var layout = new DockPanel { Margin = new Thickness(24, 20, 24, 18), LastChildFill = true };
        var commands = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 14, 0, 0) };
        var cancel = new Button { Content = "취소", IsCancel = true, Padding = new Thickness(14, 6, 14, 6), Margin = new Thickness(0, 0, 7, 0), MinHeight = 34 };
        var confirm = new Button { Content = command, Padding = new Thickness(14, 6, 14, 6), MinHeight = 34 };
        AutomationProperties.SetAutomationId(confirm, automationId);
        AutomationProperties.SetAutomationId(cancel, "CancelDialogButton");
        if (TryFindResource("PrimaryButton") is Style action) confirm.Style = action;
        commands.Children.Add(cancel);
        commands.Children.Add(confirm);
        DockPanel.SetDock(commands, Dock.Bottom);
        layout.Children.Add(commands);

        var content = new StackPanel();
        var heading = new TextBlock { Text = title, FontSize = 22, FontWeight = FontWeights.SemiBold, TextWrapping = TextWrapping.Wrap };
        AutomationProperties.SetHeadingLevel(heading, AutomationHeadingLevel.Level1);
        content.Children.Add(heading);
        content.Children.Add(new TextBlock { Text = introduction, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 6, 0, 14), Foreground = new SolidColorBrush(Color.FromRgb(72, 83, 99)) });
        foreach (var (label, input) in fields)
        {
            var caption = new Label { Content = label, Target = input, Padding = new Thickness(0, 3, 0, 4), FontWeight = FontWeights.SemiBold };
            AutomationProperties.SetLabeledBy(input, caption);
            input.Margin = new Thickness(0, 0, 0, 10);
            input.MinHeight = Math.Max(input.MinHeight, 32);
            input.Padding = new Thickness(8, 5, 8, 5);
            content.Children.Add(caption);
            content.Children.Add(input);
        }
        var error = new TextBlock { TextWrapping = TextWrapping.Wrap, Foreground = new SolidColorBrush(Color.FromRgb(130, 48, 28)), Visibility = Visibility.Collapsed };
        AutomationProperties.SetLiveSetting(error, AutomationLiveSetting.Assertive);
        content.Children.Add(error);
        confirm.Click += (_, _) =>
        {
            var message = validate();
            if (message is null) dialog.DialogResult = true;
            else { error.Text = message; error.Visibility = Visibility.Visible; }
        };
        layout.Children.Add(new ScrollViewer { Content = content, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled });
        dialog.Content = layout;
        dialog.Loaded += (_, _) =>
        {
            var first = fields.Select(field => field.Input).FirstOrDefault(input => input.IsEnabled);
            if (first is not null) first.Focus();
            else cancel.Focus();
        };
        var opener = KeyboardFocus();
        var result = dialog.ShowDialog() == true;
        opener?.Focus();
        return result;
    }

    private static Control? KeyboardFocus() => System.Windows.Input.Keyboard.FocusedElement as Control;
}
