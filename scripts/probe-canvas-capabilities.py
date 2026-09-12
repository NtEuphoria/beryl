#!/usr/bin/env python3
"""Observe immediate Canvas script-reference lifetime; no rendered-consumption claim."""
import importlib.util
from pathlib import Path

SOURCE = r'''
class BerylEngineCapsRequest : JsonApiStruct
{
    string token;
    void BerylEngineCapsRequest() { RegV("token"); }
}
class BerylEngineCapsResponse : JsonApiStruct
{
    string token;
    int executed;
    ref array<string> rows = {};
    void BerylEngineCapsResponse() { RegV("token"); RegV("executed"); RegV("rows"); }
}
class BerylCanvasTracked : TriMeshDrawCommand
{
    static int destroyed;
    void ~BerylCanvasTracked() { destroyed++; }
}
class BerylCanvasObserver
{
    BerylCanvasTracked command;
    array<ref CanvasWidgetCommand> commands;
    array<float> vertices;
}
class BerylEngineCaps : NetApiHandler
{
    override JsonApiStruct GetRequest() { return new BerylEngineCapsRequest(); }
    void Publish(CanvasWidget canvas, BerylCanvasObserver observer)
    {
        array<ref CanvasWidgetCommand> commands = {};
        BerylCanvasTracked mesh = new BerylCanvasTracked();
        mesh.m_Vertices = {0.0, 0.0, 64.0, 0.0, 64.0, 64.0, 0.0, 64.0};
        mesh.m_Indices = {0, 1, 2, 0, 2, 3};
        mesh.m_iColor = -1;
        commands.Insert(mesh);
        observer.commands = commands;
        observer.command = mesh;
        observer.vertices = mesh.m_Vertices;
        canvas.SetDrawCommands(commands);
    }
    void Empty(CanvasWidget canvas)
    {
        array<ref CanvasWidgetCommand> empty = {};
        canvas.SetDrawCommands(empty);
    }
    void Snapshot(string stage, BerylCanvasObserver observer, BerylEngineCapsResponse result)
    {
        int commands = 0;
        int command = 0;
        int vertices = 0;
        if (observer.commands) commands = 1;
        if (observer.command) command = 1;
        if (observer.vertices) vertices = 1;
        result.rows.Insert(stage + "|" + commands.ToString() + "|" + command.ToString() + "|" + vertices.ToString() + "|" + BerylCanvasTracked.destroyed.ToString());
    }
    override JsonApiStruct GetResponse(JsonApiStruct request)
    {
        BerylEngineCapsRequest req = BerylEngineCapsRequest.Cast(request);
        BerylEngineCapsResponse result = new BerylEngineCapsResponse();
        result.token = "@TOKEN@";
        if (!req || req.token != result.token) return result;
        WorkspaceWidget workspace = GetGame().GetWorkspace();
        if (!workspace) return result;
        CanvasWidget canvas = CanvasWidget.Cast(workspace.CreateWidgetInWorkspace(WidgetType.CanvasWidgetTypeID, 0, 0, 128, 128, WidgetFlags.VISIBLE, Color.FromInt(-1), 0));
        if (!canvas) return result;
        result.rows.Insert("created|1");
        BerylCanvasTracked.destroyed = 0;
        BerylCanvasObserver observer = new BerylCanvasObserver();
        Publish(canvas, observer);
        Snapshot("after-publish", observer, result);
        Empty(canvas);
        Snapshot("after-empty", observer, result);
        Publish(canvas, observer);
        Snapshot("second-publish", observer, result);
        canvas.RemoveFromHierarchy();
        canvas = null;
        Snapshot("after-remove", observer, result);
        result.executed = 1;
        return result;
    }
}
'''

if __name__ == "__main__":
    path = Path(__file__).with_name("probe-engine-capabilities.py")
    spec = importlib.util.spec_from_file_location("engine_caps", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.execute(SOURCE, "canvas-caps", 5, __file__)
