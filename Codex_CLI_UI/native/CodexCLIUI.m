#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>

@interface AppDelegate : NSObject <NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler>
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic, strong) WKWebView *webView;
@property(nonatomic, strong) NSTask *serverTask;
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
    [self buildWindow];
    [self loadStartupPage];

    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        [self ensureServerAndLoad];
    });
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    return YES;
}

- (void)buildWindow {
    NSScreen *screen = [NSScreen mainScreen];
    NSRect screenFrame = screen ? [screen visibleFrame] : NSMakeRect(0, 0, 1440, 900);
    CGFloat width = MIN(MAX(screenFrame.size.width * 0.82, 1120), 1440);
    CGFloat height = MIN(MAX(screenFrame.size.height * 0.86, 720), 960);
    NSRect frame = NSMakeRect(
        NSMidX(screenFrame) - width / 2,
        NSMidY(screenFrame) - height / 2,
        width,
        height
    );

    WKWebViewConfiguration *configuration = [[WKWebViewConfiguration alloc] init];
    configuration.defaultWebpagePreferences.allowsContentJavaScript = YES;
    configuration.preferences.javaScriptCanOpenWindowsAutomatically = NO;
    WKUserContentController *userContentController = [[WKUserContentController alloc] init];
    [userContentController addScriptMessageHandler:self name:@"codexOpenFiles"];
    configuration.userContentController = userContentController;

    self.webView = [[WKWebView alloc] initWithFrame:NSZeroRect configuration:configuration];
    self.webView.navigationDelegate = self;
    self.webView.UIDelegate = self;
    self.webView.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;

    self.window = [[NSWindow alloc]
        initWithContentRect:frame
                  styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable
                    backing:NSBackingStoreBuffered
                      defer:NO];
    self.window.title = @"Codex CLI UI";
    self.window.minSize = NSMakeSize(960, 640);
    self.window.contentView = self.webView;
    [self.window center];
    [self.window makeKeyAndOrderFront:nil];
    [NSApp activateIgnoringOtherApps:YES];
}

- (void)loadStartupPage {
    NSString *html = @"<!doctype html>"
    "<html><head><meta charset=\"utf-8\"><style>"
    "html,body{height:100%;margin:0;background:#0f1115;color:#f5f3ee;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Helvetica,Arial,sans-serif;}"
    "body{display:grid;place-items:center;}"
    ".panel{width:min(460px,calc(100vw - 48px));border:1px solid rgba(255,255,255,.14);border-radius:8px;padding:24px;background:#181b21;box-shadow:0 20px 80px rgba(0,0,0,.28);}"
    "h1{margin:0 0 10px;font-size:22px;font-weight:680;letter-spacing:0;}"
    "p{margin:0;color:rgba(245,243,238,.72);line-height:1.45;font-size:14px;}"
    "</style></head><body><main class=\"panel\">"
    "<h1>Opening Codex CLI UI</h1><p>Starting the local service and loading your workspace.</p>"
    "</main></body></html>";
    [self.webView loadHTMLString:html baseURL:nil];
}

- (void)ensureServerAndLoad {
    if (![self isServerReady]) {
        [self startServer];
    }

    for (NSInteger attempt = 0; attempt < 20; attempt++) {
        if ([self isServerReady]) {
            dispatch_async(dispatch_get_main_queue(), ^{
                NSURL *url = [NSURL URLWithString:@"http://127.0.0.1:8765/"];
                [self.webView loadRequest:[NSURLRequest requestWithURL:url]];
            });
            return;
        }
        [NSThread sleepForTimeInterval:0.35];
    }

    dispatch_async(dispatch_get_main_queue(), ^{
        [self loadErrorPage];
    });
}

- (BOOL)isServerReady {
    NSURL *url = [NSURL URLWithString:@"http://127.0.0.1:8765/api/config"];
    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url];
    request.timeoutInterval = 0.75;

    __block BOOL ok = NO;
    dispatch_semaphore_t semaphore = dispatch_semaphore_create(0);
    NSURLSessionDataTask *task = [[NSURLSession sharedSession]
        dataTaskWithRequest:request
          completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
              if ([response isKindOfClass:[NSHTTPURLResponse class]]) {
                  NSInteger status = [(NSHTTPURLResponse *)response statusCode];
                  ok = status >= 200 && status < 500;
              }
              dispatch_semaphore_signal(semaphore);
          }];

    [task resume];
    dispatch_semaphore_wait(semaphore, dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1.0 * NSEC_PER_SEC)));
    [task cancel];
    return ok;
}

- (void)startServer {
    NSString *home = NSHomeDirectory();
    NSString *appRoot = [home stringByAppendingPathComponent:@"Applications/Codex_CLI_UI"];
    NSString *serverPath = [appRoot stringByAppendingPathComponent:@"server.py"];
    if (![[NSFileManager defaultManager] fileExistsAtPath:serverPath]) {
        return;
    }

    NSTask *task = [[NSTask alloc] init];
    task.launchPath = @"/usr/bin/python3";
    task.arguments = @[serverPath];
    task.currentDirectoryPath = appRoot;
    task.standardOutput = [NSFileHandle fileHandleWithNullDevice];
    task.standardError = [NSFileHandle fileHandleWithNullDevice];

    NSMutableDictionary *environment = [[[NSProcessInfo processInfo] environment] mutableCopy];
    environment[@"CODEX_UI_HOST"] = @"127.0.0.1";
    environment[@"CODEX_UI_PORT"] = @"8765";
    environment[@"CODEX_PROFILE"] = @"manager";
    environment[@"CODEX_CWD"] = [home stringByAppendingPathComponent:@"Documents/Codex"];
    if (!environment[@"QIDI_MOONRAKER_URL"]) {
        environment[@"QIDI_MOONRAKER_URL"] = @"http://printer-host.local:7125";
    }
    environment[@"PATH"] = @"/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin";
    task.environment = environment;

    NSError *error = nil;
    if ([task launchAndReturnError:&error]) {
        self.serverTask = task;
    } else {
        self.serverTask = nil;
    }
}

- (void)loadErrorPage {
    NSString *html = @"<!doctype html>"
    "<html><head><meta charset=\"utf-8\"><style>"
    "html,body{height:100%;margin:0;background:#0f1115;color:#f5f3ee;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Helvetica,Arial,sans-serif;}"
    "body{display:grid;place-items:center;}"
    ".panel{width:min(540px,calc(100vw - 48px));border:1px solid rgba(255,105,97,.45);border-radius:8px;padding:24px;background:#181b21;}"
    "h1{margin:0 0 10px;font-size:22px;letter-spacing:0;}"
    "p{margin:0;color:rgba(245,243,238,.72);line-height:1.45;font-size:14px;}"
    "code{color:#ff8a80;}"
    "</style></head><body><main class=\"panel\">"
    "<h1>Codex CLI UI did not start</h1>"
    "<p>The native app could not reach <code>127.0.0.1:8765</code>. Try restarting the app or running <code>~/Applications/Codex_CLI_UI/start.command</code>.</p>"
    "</main></body></html>";
    [self.webView loadHTMLString:html baseURL:nil];
}

- (NSString *)contentTypeForPath:(NSString *)path {
    NSString *extension = path.pathExtension.lowercaseString ?: @"";
    NSDictionary<NSString *, NSString *> *types = @{
        @"stl": @"model/stl",
        @"step": @"model/step",
        @"stp": @"model/step",
        @"3mf": @"model/3mf",
        @"obj": @"model/obj",
        @"scad": @"text/plain",
        @"f3d": @"application/octet-stream",
        @"img": @"application/octet-stream",
        @"xz": @"application/x-xz",
        @"zip": @"application/zip",
        @"pdf": @"application/pdf",
        @"txt": @"text/plain",
        @"md": @"text/markdown",
        @"json": @"application/json",
        @"csv": @"text/csv",
        @"jpg": @"image/jpeg",
        @"jpeg": @"image/jpeg",
        @"png": @"image/png",
        @"gif": @"image/gif",
        @"webp": @"image/webp"
    };
    return types[extension] ?: @"application/octet-stream";
}

- (void)sendNativeFilePickerResponseWithRequestId:(NSString *)requestId files:(NSArray<NSDictionary *> *)files error:(NSString *)errorText {
    NSMutableDictionary *payload = [@{
        @"requestId": requestId ?: @"",
        @"files": files ?: @[]
    } mutableCopy];
    if (errorText.length) {
        payload[@"error"] = errorText;
    }

    NSError *jsonError = nil;
    NSData *data = [NSJSONSerialization dataWithJSONObject:payload options:0 error:&jsonError];
    if (!data || jsonError) {
        return;
    }
    NSString *json = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    if (!json.length) {
        return;
    }
    NSString *script = [NSString stringWithFormat:@"window.codexReceiveNativeFiles && window.codexReceiveNativeFiles(%@);", json];
    dispatch_async(dispatch_get_main_queue(), ^{
        [self.webView evaluateJavaScript:script completionHandler:nil];
    });
}

- (void)userContentController:(WKUserContentController *)userContentController didReceiveScriptMessage:(WKScriptMessage *)message {
    if (![message.name isEqualToString:@"codexOpenFiles"]) {
        return;
    }

    NSString *requestId = @"";
    if ([message.body isKindOfClass:[NSDictionary class]]) {
        id value = [(NSDictionary *)message.body objectForKey:@"requestId"];
        if ([value isKindOfClass:[NSString class]]) {
            requestId = value;
        }
    }

    NSOpenPanel *panel = [NSOpenPanel openPanel];
    panel.canChooseFiles = YES;
    panel.canChooseDirectories = NO;
    panel.allowsMultipleSelection = YES;
    panel.canCreateDirectories = NO;
    panel.prompt = @"Attach";

    [panel beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse result) {
        NSMutableArray<NSDictionary *> *files = [NSMutableArray array];
        if (result == NSModalResponseOK) {
            for (NSURL *url in panel.URLs) {
                NSString *path = url.path;
                if (!path.length) {
                    continue;
                }
                NSDictionary *attributes = [[NSFileManager defaultManager] attributesOfItemAtPath:path error:nil];
                NSNumber *size = attributes[NSFileSize] ?: @0;
                [files addObject:@{
                    @"name": path.lastPathComponent ?: @"attached file",
                    @"path": path,
                    @"size": size,
                    @"type": [self contentTypeForPath:path]
                }];
            }
        }
        [self sendNativeFilePickerResponseWithRequestId:requestId files:files error:nil];
    }];
}

- (void)webView:(WKWebView *)webView
runOpenPanelWithParameters:(WKOpenPanelParameters *)parameters
initiatedByFrame:(WKFrameInfo *)frame
completionHandler:(void (^)(NSArray<NSURL *> *URLs))completionHandler {
    NSOpenPanel *panel = [NSOpenPanel openPanel];
    panel.canChooseFiles = YES;
    panel.canChooseDirectories = parameters.allowsDirectories;
    panel.allowsMultipleSelection = parameters.allowsMultipleSelection;
    panel.canCreateDirectories = NO;
    panel.prompt = @"Attach";

    [panel beginSheetModalForWindow:self.window completionHandler:^(NSModalResponse result) {
        if (result == NSModalResponseOK) {
            completionHandler(panel.URLs);
        } else {
            completionHandler(nil);
        }
    }];
}

- (void)webView:(WKWebView *)webView
decidePolicyForNavigationAction:(WKNavigationAction *)navigationAction
decisionHandler:(void (^)(WKNavigationActionPolicy))decisionHandler {
    NSURL *url = navigationAction.request.URL;
    if (!url) {
        decisionHandler(WKNavigationActionPolicyAllow);
        return;
    }

    NSString *scheme = url.scheme.lowercaseString;
    if ([scheme isEqualToString:@"http"] || [scheme isEqualToString:@"https"]) {
        NSString *host = url.host.lowercaseString ?: @"";
        if ([host isEqualToString:@"127.0.0.1"] || [host isEqualToString:@"localhost"]) {
            decisionHandler(WKNavigationActionPolicyAllow);
            return;
        }

        if (navigationAction.navigationType == WKNavigationTypeLinkActivated) {
            [[NSWorkspace sharedWorkspace] openURL:url];
            decisionHandler(WKNavigationActionPolicyCancel);
            return;
        }
    }

    decisionHandler(WKNavigationActionPolicyAllow);
}

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *application = [NSApplication sharedApplication];
        AppDelegate *delegate = [[AppDelegate alloc] init];
        application.delegate = delegate;
        [application run];
    }
    return 0;
}
