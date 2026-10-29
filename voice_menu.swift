// Native pop-up voice menu with hover submenus, shown at the mouse pointer.
// Reads a JSON menu tree on stdin, prints the chosen voice key (empty = cancelled).
//   [{"title": "...", "key": "ada", "checked": true},
//    {"title": "Coach", "children": [{"title": "...", "key": "samara"}]}]
// Build: swiftc -O voice_menu.swift -o voice_menu
// Test without a mouse: voice_menu --test-pick <key>  (fires that item's action)
import AppKit

struct Item: Decodable {
    let title: String
    let key: String?
    let checked: Bool?
    let children: [Item]?
}

final class Picker: NSObject {
    var chosen = ""
    @objc func pick(_ sender: NSMenuItem) { chosen = sender.representedObject as? String ?? "" }
}

let picker = Picker()

func build(_ items: [Item]) -> NSMenu {
    let menu = NSMenu()
    menu.autoenablesItems = false
    for it in items {
        if it.title == "-" { menu.addItem(.separator()); continue }
        let mi = NSMenuItem(title: it.title, action: nil, keyEquivalent: "")
        if let kids = it.children {
            mi.submenu = build(kids)
        } else if let key = it.key {
            mi.target = picker
            mi.action = #selector(Picker.pick(_:))
            mi.representedObject = key
        } else {
            mi.isEnabled = false   // header line
        }
        if it.checked == true { mi.state = .on }
        menu.addItem(mi)
    }
    return menu
}

// Depth-first search for the item carrying `key`; returns (menu, index).
func find(_ menu: NSMenu, _ key: String) -> (NSMenu, Int)? {
    for (i, mi) in menu.items.enumerated() {
        if mi.representedObject as? String == key { return (menu, i) }
        if let sub = mi.submenu, let hit = find(sub, key) { return hit }
    }
    return nil
}

let data = FileHandle.standardInput.readDataToEndOfFile()
guard let items = try? JSONDecoder().decode([Item].self, from: data) else {
    FileHandle.standardError.write("voice_menu: bad JSON on stdin\n".data(using: .utf8)!)
    exit(2)
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let menu = build(items)

let args = CommandLine.arguments
if args.count == 3, args[1] == "--test-pick" {
    if let (m, i) = find(menu, args[2]) { m.performActionForItem(at: i) }
    print(picker.chosen)
    exit(0)
}

app.activate(ignoringOtherApps: true)
menu.popUp(positioning: nil, at: NSEvent.mouseLocation, in: nil)
print(picker.chosen)
